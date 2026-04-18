from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from src.models import (
    AirQualityPayload,
    CarParkPayload,
    EnergyMeterPayload,
    GeoLocation,
    SensorMetadata,
    SensorReading,
    SensorType,
    TrafficLightPayload,
    TrafficLightState,
)


class TestSensorType:
    def test_enum_values(self):
        assert SensorType.CAR_PARK == "car_park"
        assert SensorType.TRAFFIC_LIGHT == "traffic_light"
        assert SensorType.AIR_QUALITY == "air_quality"
        assert SensorType.ENERGY_METER == "energy_meter"


class TestGeoLocation:
    def test_valid(self):
        loc = GeoLocation(latitude=50.45, longitude=30.52)
        assert loc.latitude == 50.45

    def test_latitude_out_of_range_raises(self):
        with pytest.raises(ValidationError):
            GeoLocation(latitude=95.0, longitude=0.0)

    def test_longitude_out_of_range_raises(self):
        with pytest.raises(ValidationError):
            GeoLocation(latitude=0.0, longitude=181.0)


class TestCarParkPayload:
    def test_occupancy_rate_computed(self):
        p = CarParkPayload(total_spots=100, occupied_spots=25)
        assert p.occupancy_rate == 0.25
        assert p.kind == "car_park"

    def test_occupied_exceeds_total_raises(self):
        with pytest.raises(ValidationError):
            CarParkPayload(total_spots=10, occupied_spots=11)

    def test_total_spots_must_be_positive(self):
        with pytest.raises(ValidationError):
            CarParkPayload(total_spots=0, occupied_spots=0)


class TestTrafficLightPayload:
    def test_valid(self):
        p = TrafficLightPayload(state="green", cycle_seconds=90, queue_length=5)
        assert p.state is TrafficLightState.GREEN
        assert p.kind == "traffic_light"

    def test_unknown_state_raises(self):
        with pytest.raises(ValidationError):
            TrafficLightPayload(state="purple", cycle_seconds=60, queue_length=0)


class TestAirQualityPayload:
    def test_valid(self):
        p = AirQualityPayload(
            pm2_5=12.5,
            pm10=20.0,
            no2=15.0,
            temperature_c=10.0,
            humidity_percent=70.0,
        )
        assert p.kind == "air_quality"
        assert p.o3 is None

    def test_humidity_out_of_range_raises(self):
        with pytest.raises(ValidationError):
            AirQualityPayload(pm2_5=1, pm10=1, no2=1, temperature_c=0, humidity_percent=150.0)


class TestEnergyMeterPayload:
    def test_valid(self):
        p = EnergyMeterPayload(
            power_kw=4.1,
            voltage_v=230.0,
            current_a=18.0,
            cumulative_kwh=120.5,
            power_factor=0.92,
        )
        assert p.kind == "energy_meter"


class TestSensorReadingDiscriminator:
    """Перевірка, що дискримінована спілка вірно обирає конкретний payload."""

    def _metadata(self, sensor_type: SensorType) -> SensorMetadata:
        return SensorMetadata(
            sensor_id="test-001",
            sensor_type=sensor_type,
            location=GeoLocation(latitude=50.45, longitude=30.52),
            timestamp=datetime(2026, 4, 17, 10, 0, tzinfo=timezone.utc),
        )

    def test_car_park_payload_resolved(self):
        reading = SensorReading.model_validate(
            {
                "metadata": self._metadata(SensorType.CAR_PARK).model_dump(mode="json"),
                "payload": {"kind": "car_park", "total_spots": 50, "occupied_spots": 10},
            }
        )
        assert isinstance(reading.payload, CarParkPayload)
        assert reading.payload.total_spots == 50

    def test_traffic_light_payload_resolved(self):
        reading = SensorReading.model_validate(
            {
                "metadata": self._metadata(SensorType.TRAFFIC_LIGHT).model_dump(mode="json"),
                "payload": {
                    "kind": "traffic_light",
                    "state": "red",
                    "cycle_seconds": 60,
                    "queue_length": 3,
                },
            }
        )
        assert isinstance(reading.payload, TrafficLightPayload)
        assert reading.payload.state is TrafficLightState.RED

    def test_unknown_kind_raises(self):
        with pytest.raises(ValidationError):
            SensorReading.model_validate(
                {
                    "metadata": self._metadata(SensorType.AIR_QUALITY).model_dump(mode="json"),
                    "payload": {"kind": "radiation", "value": 0.12},
                }
            )

    def test_sensor_type_payload_kind_mismatch_raises(self):
        with pytest.raises(ValidationError):
            SensorReading.model_validate(
                {
                    "metadata": self._metadata(SensorType.CAR_PARK).model_dump(mode="json"),
                    "payload": {
                        "kind": "traffic_light",
                        "state": "red",
                        "cycle_seconds": 60,
                        "queue_length": 3,
                    },
                }
            )
