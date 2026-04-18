import pytest


@pytest.fixture
def sample_sensor_readings() -> list[dict]:
    """Вибірковий пакет універсальних показань різних типів."""
    return [
        {
            "metadata": {
                "sensor_id": "car_park-001",
                "sensor_type": "car_park",
                "location": {"latitude": 50.45, "longitude": 30.52},
                "timestamp": "2026-04-17T10:00:00Z",
            },
            "payload": {
                "kind": "car_park",
                "total_spots": 100,
                "occupied_spots": 42,
                "avg_stay_minutes": 65.0,
            },
        },
        {
            "metadata": {
                "sensor_id": "tl-005",
                "sensor_type": "traffic_light",
                "location": {"latitude": 50.44, "longitude": 30.51},
                "timestamp": "2026-04-17T10:01:00Z",
            },
            "payload": {
                "kind": "traffic_light",
                "state": "red",
                "cycle_seconds": 90,
                "queue_length": 4,
                "pedestrian_request": False,
            },
        },
    ]


class TestPostSensorReadings:
    async def test_creates_records_returns_201(self, client, sample_sensor_readings):
        response = await client.post("/sensor_readings/", json=sample_sensor_readings)
        assert response.status_code == 201

    async def test_response_contains_ids(self, client, sample_sensor_readings):
        response = await client.post("/sensor_readings/", json=sample_sensor_readings)
        data = response.json()
        assert len(data) == 2
        assert all("id" in r for r in data)

    async def test_payload_persisted_as_json(self, client, sample_sensor_readings):
        response = await client.post("/sensor_readings/", json=sample_sensor_readings)
        data = response.json()
        car_park = next(r for r in data if r["sensor_type"] == "car_park")
        assert car_park["payload"]["total_spots"] == 100
        assert car_park["payload"]["kind"] == "car_park"

    async def test_unknown_payload_kind_returns_422(self, client):
        bad = [
            {
                "metadata": {
                    "sensor_id": "x-1",
                    "sensor_type": "car_park",
                    "location": {"latitude": 0.0, "longitude": 0.0},
                    "timestamp": "2026-04-17T10:00:00Z",
                },
                "payload": {"kind": "radiation", "value": 1.0},
            }
        ]
        response = await client.post("/sensor_readings/", json=bad)
        assert response.status_code == 422


class TestListSensorReadings:
    async def test_returns_all_without_filter(self, client, sample_sensor_readings):
        await client.post("/sensor_readings/", json=sample_sensor_readings)
        response = await client.get("/sensor_readings/")
        assert response.status_code == 200
        assert len(response.json()) == 2

    async def test_filter_by_type(self, client, sample_sensor_readings):
        await client.post("/sensor_readings/", json=sample_sensor_readings)
        response = await client.get("/sensor_readings/?sensor_type=car_park")
        body = response.json()
        assert len(body) == 1
        assert body[0]["sensor_type"] == "car_park"

    async def test_filter_by_sensor_id(self, client, sample_sensor_readings):
        await client.post("/sensor_readings/", json=sample_sensor_readings)
        response = await client.get("/sensor_readings/?sensor_id=tl-005")
        body = response.json()
        assert len(body) == 1
        assert body[0]["sensor_id"] == "tl-005"


class TestGetSensorReadingById:
    async def test_returns_404_when_missing(self, client):
        response = await client.get("/sensor_readings/9999")
        assert response.status_code == 404

    async def test_returns_record(self, client, sample_sensor_readings):
        created = await client.post("/sensor_readings/", json=sample_sensor_readings)
        record_id = created.json()[0]["id"]
        response = await client.get(f"/sensor_readings/{record_id}")
        assert response.status_code == 200
        assert response.json()["id"] == record_id


class TestDeleteSensorReading:
    async def test_deletes_existing(self, client, sample_sensor_readings):
        created = await client.post("/sensor_readings/", json=sample_sensor_readings)
        record_id = created.json()[0]["id"]
        response = await client.delete(f"/sensor_readings/{record_id}")
        assert response.status_code == 200

        missing = await client.get(f"/sensor_readings/{record_id}")
        assert missing.status_code == 404
