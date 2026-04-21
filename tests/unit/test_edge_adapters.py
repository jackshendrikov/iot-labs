from datetime import datetime, timezone
from types import SimpleNamespace

from src.edge.adapters import AgentMqttAdapter, HubMqttAdapter
from src.models import Accelerometer, AggregatedData, Gps, ProcessedAgentData, RoadState


class FakeMqttClient:
    def __init__(self) -> None:
        self.connected_to: tuple[str, int] | None = None
        self.subscriptions: list[str] = []
        self.publications: list[tuple[str, str]] = []
        self.loop_started = False
        self.disconnected = False
        self.on_connect = None
        self.on_message = None

    def connect(self, host: str, port: int) -> None:
        self.connected_to = (host, port)

    def subscribe(self, topic: str) -> None:
        self.subscriptions.append(topic)

    def publish(self, topic: str, payload: str) -> SimpleNamespace:
        self.publications.append((topic, payload))
        return SimpleNamespace(rc=0)

    def loop_start(self) -> None:
        self.loop_started = True

    def loop_stop(self) -> None:
        self.loop_started = False

    def loop_forever(self) -> None:
        return None

    def disconnect(self) -> None:
        self.disconnected = True


class FakeHubGateway:
    def __init__(self) -> None:
        self.connected = False
        self.stopped = False
        self.sent_data: list[ProcessedAgentData] = []

    def connect(self) -> None:
        self.connected = True

    def send_data(self, processed_data: ProcessedAgentData) -> bool:
        self.sent_data.append(processed_data)
        return True

    def stop(self) -> None:
        self.stopped = True


def _make_agent_data(*, y: float = 600.0, z: float = 16500.0) -> AggregatedData:
    return AggregatedData(
        accelerometer=Accelerometer(x=0.1, y=y, z=z),
        gps=Gps(latitude=50.45, longitude=30.52),
        time=datetime(2026, 3, 20, 11, 0, tzinfo=timezone.utc),
    )


class TestHubMqttAdapter:
    def test_publishes_processed_data_to_configured_topic(self):
        mqtt_client = FakeMqttClient()
        adapter = HubMqttAdapter(
            mqtt_client=mqtt_client,
            broker_host="mqtt",
            broker_port=1883,
            topic="processed_agent_data_topic",
        )

        adapter.connect()
        result = adapter.send_data(ProcessedAgentData(road_state=RoadState.WARNING, agent_data=_make_agent_data()))

        assert result is True
        assert mqtt_client.connected_to == ("mqtt", 1883)
        assert mqtt_client.loop_started is True
        assert mqtt_client.publications
        assert mqtt_client.publications[0][0] == "processed_agent_data_topic"


class TestAgentMqttAdapter:
    def test_connect_connects_hub_and_mqtt_client(self):
        hub = FakeHubGateway()
        mqtt_client = FakeMqttClient()
        adapter = AgentMqttAdapter(
            hub_gateway=hub,
            mqtt_client=mqtt_client,
            broker_host="mqtt",
            broker_port=1883,
            topic="agent_data_topic",
        )

        adapter.connect()

        assert hub.connected is True
        assert mqtt_client.connected_to == ("mqtt", 1883)

    def test_on_connect_subscribes_to_agent_topic(self):
        hub = FakeHubGateway()
        mqtt_client = FakeMqttClient()
        adapter = AgentMqttAdapter(hub_gateway=hub, mqtt_client=mqtt_client, topic="agent_data_topic")

        adapter._on_connect(mqtt_client, None, None, 0, None)

        assert mqtt_client.subscriptions == ["agent_data_topic"]

    def test_on_message_processes_payload_and_sends_to_hub(self):
        hub = FakeHubGateway()
        mqtt_client = FakeMqttClient()
        adapter = AgentMqttAdapter(hub_gateway=hub, mqtt_client=mqtt_client)
        payload = _make_agent_data(y=15100.0).model_dump_json().encode("utf-8")
        message = SimpleNamespace(payload=payload)

        adapter.on_message(mqtt_client, None, message)

        assert len(hub.sent_data) == 1
        assert hub.sent_data[0].road_state is RoadState.BAD

    def test_on_message_ignores_invalid_payload(self):
        hub = FakeHubGateway()
        mqtt_client = FakeMqttClient()
        adapter = AgentMqttAdapter(hub_gateway=hub, mqtt_client=mqtt_client)
        message = SimpleNamespace(payload=b"not-json")

        adapter.on_message(mqtt_client, None, message)

        assert hub.sent_data == []

    def test_stop_disconnects_mqtt_and_hub(self):
        hub = FakeHubGateway()
        mqtt_client = FakeMqttClient()
        adapter = AgentMqttAdapter(hub_gateway=hub, mqtt_client=mqtt_client)

        adapter.stop()

        assert mqtt_client.disconnected is True
        assert hub.stopped is True
