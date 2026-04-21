"""MQTT edge-сервіс для універсальних сенсорів."""

from typing import Any

import paho.mqtt.client as mqtt
from paho.mqtt.client import MQTTMessage

from src.core.config import settings
from src.core.logger import logger
from src.models.sensor_reading import SensorReading
from src.sensors_edge.anomaly_rules import detect_anomaly_flags


class SensorsEdgeService:
    """Edge-рівень для універсальних сенсорів: підписка, розмітка та публікація."""

    def __init__(
        self,
        *,
        mqtt_client: mqtt.Client | None = None,
        broker_host: str | None = None,
        broker_port: int | None = None,
        source_topic: str | None = None,
        sink_topic: str | None = None,
    ) -> None:
        self._client = mqtt_client or mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
        self._broker_host = broker_host or settings.mqtt_broker_host
        self._broker_port = broker_port or settings.mqtt_broker_port
        self._source_topic = source_topic or settings.sensors_mqtt_topic
        self._sink_topic = sink_topic or settings.sensors_hub_mqtt_topic
        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message

    def connect(self) -> None:
        """Підключається до MQTT-брокера."""
        self._client.connect(self._broker_host, self._broker_port)

    def start(self) -> None:
        """Запускає блокуючий MQTT loop."""
        self._client.loop_forever()

    def stop(self) -> None:
        """Коректно розриває MQTT-зʼєднання."""
        self._client.disconnect()

    def _on_connect(
        self,
        client: mqtt.Client,
        userdata: Any,  # noqa: ARG002
        flags: Any,  # noqa: ARG002
        reason_code: Any,
        properties: Any,  # noqa: ARG002
    ) -> None:
        """Після підключення підписується на MQTT-топік сенсорного агента."""
        if reason_code == 0:
            client.subscribe(self._source_topic)
            logger.info(
                f"Sensors Edge підключено, підписка на '{self._source_topic}', публікація в '{self._sink_topic}'"
            )
            return
        logger.error(f"Sensors Edge MQTT: помилка підключення, код {reason_code}")

    def _on_message(self, client: mqtt.Client, userdata: Any, msg: MQTTMessage) -> None:  # noqa: ARG002
        """Розбирає повідомлення, додає `anomaly_flags` і публікує його в топік Hub."""
        try:
            reading = SensorReading.model_validate_json(msg.payload.decode("utf-8"))
        except Exception:
            logger.exception("Sensors Edge: не вдалося розпарсити MQTT-повідомлення")
            return

        try:
            flags = detect_anomaly_flags(reading.payload)
            # Об'єднуємо з уже наявними прапорцями, якщо їх додав сам пристрій.
            existing = set(reading.metadata.anomaly_flags)
            merged = list(existing.union(flags))
            enriched = reading.model_copy(
                update={"metadata": reading.metadata.model_copy(update={"anomaly_flags": merged})}
            )
        except Exception:
            logger.exception("Sensors Edge: помилка оцінки правил аномалій")
            return

        payload = enriched.model_dump_json()
        result = self._client.publish(self._sink_topic, payload)
        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            logger.warning(f"Sensors Edge: не вдалося опублікувати у '{self._sink_topic}', код {result.rc}")
            return

        if flags:
            logger.info(
                f"Sensors Edge: {reading.metadata.sensor_type.value}/{reading.metadata.sensor_id} -> прапорці {flags}"
            )
        else:
            logger.debug(f"Sensors Edge: {reading.metadata.sensor_type.value}/{reading.metadata.sensor_id} -> ok")


def run() -> None:
    """Точка входу Sensors Edge."""
    service = SensorsEdgeService()
    try:
        service.connect()
        logger.info("Sensors Edge запущено")
        service.start()
    except KeyboardInterrupt:
        logger.info("Sensors Edge зупинено за запитом користувача")
    finally:
        service.stop()


if __name__ == "__main__":
    run()
