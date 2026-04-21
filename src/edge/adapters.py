from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any

import paho.mqtt.client as mqtt
from paho.mqtt.client import MQTTMessage

from src.core.config import settings
from src.core.logger import logger
from src.edge.processor import process_agent_data
from src.models.aggregated_data import AggregatedData
from src.models.processed_agent_data import ProcessedAgentData

Processor = Callable[[AggregatedData], ProcessedAgentData]


class AgentGateway(ABC):
    """Абстракція для джерела даних від агента."""

    @abstractmethod
    def connect(self) -> None:
        """Підключає транспортний шар до зовнішніх сервісів."""

    @abstractmethod
    def start(self) -> None:
        """Запускає прийом повідомлень."""

    @abstractmethod
    def stop(self) -> None:
        """Коректно завершує роботу транспортного шару."""


class HubGateway(ABC):
    """Абстракція для відправки оброблених даних у Hub."""

    @abstractmethod
    def connect(self) -> None:
        """Підключає транспортний шар до зовнішніх сервісів."""

    @abstractmethod
    def send_data(self, processed_data: ProcessedAgentData) -> bool:
        """Відправляє оброблені дані в Hub."""

    @abstractmethod
    def stop(self) -> None:
        """Коректно завершує роботу транспортного шару."""


class HubMqttAdapter(HubGateway):
    """Публікує ProcessedAgentData у Hub через MQTT."""

    def __init__(
        self,
        mqtt_client: mqtt.Client | None = None,
        *,
        broker_host: str | None = None,
        broker_port: int | None = None,
        topic: str | None = None,
    ) -> None:
        self._client = mqtt_client or mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
        self._broker_host = broker_host or settings.mqtt_broker_host
        self._broker_port = broker_port or settings.mqtt_broker_port
        self._topic = topic or settings.hub_mqtt_topic
        self._connected = False

    def connect(self) -> None:
        """Підключається до MQTT-брокера та запускає loop."""
        if self._connected:
            return

        self._client.connect(self._broker_host, self._broker_port)
        self._client.loop_start()
        self._connected = True

    def send_data(self, processed_data: ProcessedAgentData) -> bool:
        """Публікує ProcessedAgentData у сконфігурований MQTT-топік."""
        try:
            result = self._client.publish(self._topic, processed_data.model_dump_json())
        except Exception:
            logger.exception("Помилка публікації ProcessedAgentData в Hub через MQTT")
            return False

        if result.rc == mqtt.MQTT_ERR_SUCCESS:
            logger.debug(f"Edge -> Hub MQTT: {processed_data.road_state} @ {self._topic}")
            return True

        logger.warning(f"Помилка публікації в MQTT з кодом {result.rc}")
        return False

    def stop(self) -> None:
        """Зупиняє MQTT loop та розриває з'єднання."""
        if not self._connected:
            return

        self._client.loop_stop()
        self._client.disconnect()
        self._connected = False


class AgentMqttAdapter(AgentGateway):
    """Підписується на дані агента, обробляє їх та передає у Hub."""

    def __init__(
        self,
        hub_gateway: HubGateway,
        *,
        mqtt_client: mqtt.Client | None = None,
        processor: Processor = process_agent_data,
        broker_host: str | None = None,
        broker_port: int | None = None,
        topic: str | None = None,
    ) -> None:
        self._hub = hub_gateway
        self._processor = processor
        self._client = mqtt_client or mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
        self._broker_host = broker_host or settings.mqtt_broker_host
        self._broker_port = broker_port or settings.mqtt_broker_port
        self._topic = topic or settings.mqtt_topic
        self._client.on_connect = self._on_connect
        self._client.on_message = self.on_message

    def connect(self) -> None:
        """Підключається до Hub та MQTT-брокера."""
        self._hub.connect()
        self._client.connect(self._broker_host, self._broker_port)

    def start(self) -> None:
        """Запускає нескінченний MQTT loop для прийому повідомлень."""
        self._client.loop_forever()

    def stop(self) -> None:
        """Розриває MQTT-з'єднання та зупиняє Hub gateway."""
        self._client.disconnect()
        self._hub.stop()

    def _on_connect(
        self,
        client: mqtt.Client,
        userdata: Any,
        flags: Any,
        reason_code: Any,
        properties: Any,
    ) -> None:
        """Після підключення підписується на MQTT-топік агента."""
        if reason_code == 0:
            client.subscribe(self._topic)
            logger.info(f"Edge підключено, підписка на '{self._topic}'")
            return

        logger.error(f"Edge MQTT: помилка підключення, код {reason_code}")

    def on_message(self, client: mqtt.Client, userdata: Any, msg: MQTTMessage) -> None:
        """Обробляє повідомлення від агента та передає результат у Hub."""
        try:
            agent_data = AggregatedData.model_validate_json(msg.payload.decode("utf-8"))
            processed_data = self._processor(agent_data)
            self._hub.send_data(processed_data)
        except Exception:
            logger.exception("Помилка обробки MQTT-повідомлення у Edge")
