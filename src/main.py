import sys
import time

from paho.mqtt import client as mqtt_client

from src.config import settings
from src.domain import AggregatedData
from src.file_datasource import FileDatasource
from src.logger import logger


def connect_mqtt() -> mqtt_client.Client:
    """Створює та налаштовує MQTT‑клієнт."""

    host, port = settings.mqtt_broker_host, settings.mqtt_broker_port

    def on_connect(client: mqtt_client.Client, userdata, flags, rc) -> None:
        """Обробляє подію підключення до MQTT‑брокера."""
        match rc:
            case 0:
                logger.info(f"Підключено до брокера MQTT {host}:{port}")
            case _:
                logger.error(f"Не вдалося підключитись до {host}:{port}, код: {rc}")
                sys.exit(rc)

    # Створюємо клієнт та призначаємо обробник підключення
    client = mqtt_client.Client()
    client.on_connect = on_connect
    client.connect(host, port)
    client.loop_start()
    return client


def publish_loop(client: mqtt_client.Client, datasource: FileDatasource) -> None:
    """Нескінченно читає дані та відправляє їх у MQTT."""
    datasource.start_reading()
    try:
        while True:
            time.sleep(settings.delay)
            records: list[AggregatedData] = datasource.read()
            for record in records:
                msg = record.model_dump_json()
                result = client.publish(settings.mqtt_topic, msg)
                status = result[0]
                if status != 0:
                    logger.warning(f"Не вдалося відправити повідомлення в топік {settings.mqtt_topic}")
    except KeyboardInterrupt:
        logger.info("Завершення за запитом користувача.")
    finally:
        datasource.stop_reading()
        client.loop_stop()


def run() -> None:
    """Запускає агента."""
    client = connect_mqtt()
    datasource = FileDatasource(
        accelerometer_filename=settings.accelerometer_file,
        gps_filename=settings.gps_file,
        temperature_filename=settings.temperature_file,
        batch_size=settings.batch_size,
    )
    publish_loop(client, datasource)


if __name__ == "__main__":
    run()
