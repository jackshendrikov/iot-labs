"""Сервіс накопичення та пакетного збереження універсальних сенсорних даних."""

import asyncio
from collections.abc import Awaitable
from typing import Any, cast

import paho.mqtt.client as mqtt
import redis.asyncio as aioredis

from src.core.config import settings
from src.core.logger import logger
from src.models.sensor_reading import SensorReading
from src.sensors_hub.gateway import SensorStoreApiGateway

_REDIS_KEY = "sensors_hub:sensor_readings"


class SensorsHubService:
    """Накопичує показання сенсорів та пакетно зберігає їх у Store API."""

    def __init__(
        self,
        *,
        gateway: SensorStoreApiGateway | None = None,
        redis_client: aioredis.Redis | None = None,
        mqtt_client: mqtt.Client | None = None,
        batch_size: int | None = None,
        flush_interval_seconds: float | None = None,
    ) -> None:
        self._gateway = gateway or SensorStoreApiGateway()
        self._owns_gateway = gateway is None
        self._redis = redis_client
        self._owns_redis = redis_client is None
        self._batch_size = batch_size or settings.sensors_hub_batch_size
        self._flush_interval_seconds = flush_interval_seconds or settings.sensors_hub_flush_interval_seconds

        self._queue: asyncio.Queue[SensorReading] = asyncio.Queue()
        self._buffer: list[SensorReading] = []
        self._flush_lock = asyncio.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._processor_task: asyncio.Task[None] | None = None
        self._flush_task: asyncio.Task[None] | None = None
        self._running = False

        self._mqtt = mqtt_client or mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
        self._mqtt.on_connect = self._on_connect
        self._mqtt.on_message = self._on_message

    async def start(self, *, enable_mqtt: bool = True) -> None:
        """Запускає Hub: Redis, фонові воркери й, за потреби, MQTT-транспорт."""
        if self._running:
            return

        self._loop = asyncio.get_running_loop()
        self._running = True

        if self._redis is None:
            self._redis = await aioredis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
        logger.info("Sensors Hub: Redis підключено")

        self._processor_task = asyncio.create_task(self._process_loop())
        self._flush_task = asyncio.create_task(self._periodic_flush_loop())

        if enable_mqtt:
            self._mqtt.connect(settings.mqtt_broker_host, settings.mqtt_broker_port)
            self._mqtt.loop_start()
            logger.info(
                f"Sensors Hub запущено: MQTT={settings.sensors_hub_mqtt_topic}, "
                f"batch_size={self._batch_size}, flush_interval={self._flush_interval_seconds}s"
            )
            return

        logger.info(
            f"Sensors Hub запущено без MQTT, batch_size={self._batch_size}, "
            f"flush_interval={self._flush_interval_seconds}s"
        )

    async def stop(self) -> None:
        """Зупиняє Hub, дочищає буфер та звільняє ресурси."""
        if not self._running and self._processor_task is None and self._flush_task is None:
            return

        self._running = False
        self._mqtt.loop_stop()
        self._mqtt.disconnect()

        await self._queue.join()
        await self.flush(force=True)

        await self._cancel_task(self._flush_task)
        await self._cancel_task(self._processor_task)
        self._flush_task = None
        self._processor_task = None

        if self._redis is not None and self._owns_redis:
            await self._redis.aclose()
            self._redis = None

        if self._owns_gateway:
            await self._gateway.close()

        logger.info("Sensors Hub зупинено")

    async def ingest(self, data: SensorReading) -> None:
        """Приймає валідоване показання з будь-якого транспортного шару."""
        if not self._running:
            raise RuntimeError("SensorsHubService не запущено")
        await self._queue.put(data)

    @staticmethod
    def _on_connect(
        client: mqtt.Client,
        userdata: Any,  # noqa: ARG004
        connect_flags: Any,  # noqa: ARG004
        reason_code: Any,
        properties: Any,  # noqa: ARG004
    ) -> None:
        """Підписує MQTT-клієнт на топік Sensors Hub після успішного connect."""
        if reason_code == 0:
            client.subscribe(settings.sensors_hub_mqtt_topic)
            logger.info(f"Sensors Hub MQTT: підписка на '{settings.sensors_hub_mqtt_topic}'")
            return
        logger.error(f"Sensors Hub MQTT: помилка підключення, код {reason_code}")

    def _on_message(self, client: mqtt.Client, userdata: Any, msg: mqtt.MQTTMessage) -> None:  # noqa: ARG002
        """Отримує MQTT-повідомлення та кладе в asyncio-чергу thread-safe."""
        try:
            data = SensorReading.model_validate_json(msg.payload.decode("utf-8"))
            if self._loop is None:
                raise RuntimeError("Event loop is not initialized")
            self._loop.call_soon_threadsafe(self._queue.put_nowait, data)
        except Exception:
            logger.exception("Sensors Hub: помилка розбору MQTT-повідомлення")

    async def _process_loop(self) -> None:
        """Читає з черги, накопичує batch та відправляє його в Store API."""
        while True:
            try:
                item = await self._queue.get()
            except asyncio.CancelledError:
                break

            try:
                self._buffer.append(item)
                logger.debug(f"Sensors Hub буфер: {len(self._buffer)}/{self._batch_size}")
                if len(self._buffer) >= self._batch_size:
                    await self.flush()
            except Exception:
                logger.exception("Sensors Hub: помилка в циклі обробки")
            finally:
                self._queue.task_done()

    async def _periodic_flush_loop(self) -> None:
        """Періодично ініціює примусовий flush накопичених сенсорних даних."""
        while True:
            try:
                await asyncio.sleep(self._flush_interval_seconds)
            except asyncio.CancelledError:
                break

            try:
                await self.flush(force=True)
            except Exception:
                logger.exception("Sensors Hub: помилка періодичного flush")

    async def flush(self, *, force: bool = False) -> bool:
        """Надсилає backlog з Redis, а потім поточний буфер у Store API."""
        async with self._flush_lock:
            backlog_flushed = await self._flush_redis_backlog(force=force)
            if not backlog_flushed:
                return False

            return await self._flush_memory_buffer(force=force)

    async def _flush_memory_buffer(self, *, force: bool) -> bool:
        """Надсилає поточний буфер до Store API або переносить його в Redis backlog."""
        while self._buffer and (force or len(self._buffer) >= self._batch_size):
            batch_size = min(len(self._buffer), self._batch_size)
            batch = list(self._buffer[:batch_size])

            success = await self._gateway.save_batch(batch)
            if success:
                del self._buffer[:batch_size]
                continue

            await self._persist_backlog(batch)
            del self._buffer[:batch_size]
            logger.warning(f"Sensors Hub: не вдалося зберегти батч, {len(batch)} записів переміщено у Redis backlog")
            return False

        return True

    async def _flush_redis_backlog(self, *, force: bool) -> bool:
        """Пробує відновити раніше неуспішно збережені batch-і з Redis backlog."""
        assert self._redis is not None
        redis_client = cast(aioredis.Redis, self._redis)

        while True:
            raw_items = await cast(
                Awaitable[list[str]],
                redis_client.lrange(_REDIS_KEY, 0, self._batch_size - 1),
            )
            if not raw_items:
                return True

            if not force and len(raw_items) < self._batch_size:
                return True

            batch = [SensorReading.model_validate_json(item) for item in raw_items]
            success = await self._gateway.save_batch(batch)
            if not success:
                logger.warning(
                    f"Sensors Hub: backlog Redis не відновлено, у черзі залишається {len(raw_items)} записів"
                )
                return False

            await cast(Awaitable[str], redis_client.ltrim(_REDIS_KEY, len(raw_items), -1))

    async def _persist_backlog(self, batch: list[SensorReading]) -> None:
        """Складає невдалий batch сенсорів у Redis для повторної відправки."""
        assert self._redis is not None
        redis_client = cast(aioredis.Redis, self._redis)
        if not batch:
            return
        await cast(
            Awaitable[int],
            redis_client.rpush(_REDIS_KEY, *[item.model_dump_json() for item in batch]),
        )

    @staticmethod
    async def _cancel_task(task: asyncio.Task[None] | None) -> None:
        """Скасовує asyncio-task і тихо очікує її завершення."""
        if task is None:
            return
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
