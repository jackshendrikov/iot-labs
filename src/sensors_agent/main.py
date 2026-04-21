"""Точка входу та логіка публікації для Sensors Agent."""

import sys
import time
from datetime import UTC, datetime

from paho.mqtt import client as mqtt_client

from src.core.config import settings
from src.core.logger import logger
from src.models.sensor_reading import SensorReading
from src.models.sensor_type import SensorType
from src.sensors_agent.csv_source import MultiSensorCsvSource


def connect_mqtt() -> mqtt_client.Client:
    """Створює та налаштовує MQTT-клієнт для Sensors Agent."""
    host, port = settings.mqtt_broker_host, settings.mqtt_broker_port

    def on_connect(client: mqtt_client.Client, userdata, flags, rc) -> None:  # noqa: ARG001
        """Обробляє подію підключення до MQTT-брокера."""
        match rc:
            case 0:
                logger.info(f"Sensors Agent підключено до брокера MQTT {host}:{port}")
            case _:
                logger.error(f"Sensors Agent не зміг підключитись до {host}:{port}, код: {rc}")
                sys.exit(rc)

    client = mqtt_client.Client()
    client.on_connect = on_connect
    client.connect(host, port)
    client.loop_start()
    return client


def publish_stream(client: mqtt_client.Client, source: MultiSensorCsvSource) -> None:
    """Читає показання з CSV та публікує їх у MQTT до вичерпання джерел."""
    topic = settings.sensors_mqtt_topic
    loop_reading = settings.sensors_loop_reading
    published = 0

    try:
        while True:
            for readings in source.iter_time_slices():
                timestamp = datetime.now(UTC).replace(microsecond=0)
                payloads = [_stamp_for_live_stream(reading, timestamp).model_dump_json() for reading in readings]
                _publish_batch(client, topic, payloads)
                published += len(payloads)
                time.sleep(settings.sensors_delay)

            if not loop_reading:
                break

            logger.info("Sensors Agent повторює відтворення CSV-потоку з початку.")
            time.sleep(settings.sensors_delay)

        logger.info(f"Sensors Agent завершив публікацію, всього відправлено {published} показань.")
    except KeyboardInterrupt:
        logger.info("Sensors Agent зупинено за запитом користувача.")
    finally:
        client.loop_stop()
        client.disconnect()


def _publish_batch(client: mqtt_client.Client, topic: str, batch: list[str]) -> None:
    """Публікує кожне повідомлення з батча в MQTT та логує невдалі спроби."""
    for msg in batch:
        result = client.publish(topic, msg)
        if result[0] != 0:
            logger.warning(f"Не вдалося відправити показання в топік {topic} (код {result[0]})")


def _stamp_for_live_stream(reading: SensorReading, timestamp: datetime) -> SensorReading:
    """Повертає копію показання з оновленим timestamp для live-потоку."""
    metadata = reading.metadata.model_copy(update={"timestamp": timestamp})
    return reading.model_copy(update={"metadata": metadata})


def run() -> None:
    """Точка входу Sensors Agent."""
    client = connect_mqtt()
    source = MultiSensorCsvSource(
        {
            SensorType.CAR_PARK: settings.car_parks_file,
            SensorType.TRAFFIC_LIGHT: settings.traffic_lights_file,
            SensorType.AIR_QUALITY: settings.air_quality_file,
            SensorType.ENERGY_METER: settings.energy_meters_file,
        }
    )
    publish_stream(client, source)


if __name__ == "__main__":
    run()
