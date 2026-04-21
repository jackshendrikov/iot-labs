"""Тести для генератора синтетичних сенсорних даних."""

import shutil
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from src.models import AirQualityPayload, EnergyMeterPayload, SensorReading, SensorType, TrafficLightPayload
from src.sensors_edge.anomaly_rules import detect_anomaly_flags
from src.synthetic.generator import generate_readings, read_csv_file, write_csv_files

_OUTPUT_DIR = Path(".pytest-tmp") / "synthetic-generator"
_REQUIRED_FLAGS_BY_TYPE: dict[SensorType, set[str]] = {
    SensorType.CAR_PARK: {"overcrowded", "long_stay"},
    SensorType.TRAFFIC_LIGHT: {"congested", "gridlock", "signal_off"},
    SensorType.AIR_QUALITY: {"unhealthy_pm25", "very_unhealthy_pm25", "high_no2", "high_o3"},
    SensorType.ENERGY_METER: {"voltage_out_of_range", "poor_power_factor", "power_overload"},
}


def _cleanup_output_dir() -> None:
    shutil.rmtree(_OUTPUT_DIR, ignore_errors=True)


def _readings_by_sensor_id(readings: list[SensorReading], sensor_id: str) -> list[SensorReading]:
    return sorted(
        (reading for reading in readings if reading.metadata.sensor_id == sensor_id),
        key=lambda reading: reading.metadata.timestamp,
    )


def test_generate_readings_produces_all_required_anomaly_flags() -> None:
    readings = generate_readings(seed=42)
    flags_by_type: dict[SensorType, set[str]] = defaultdict(set)

    for reading in readings:
        flags_by_type[reading.metadata.sensor_type].update(detect_anomaly_flags(reading.payload))

    for sensor_type, required_flags in _REQUIRED_FLAGS_BY_TYPE.items():
        assert required_flags <= flags_by_type[sensor_type]


def test_generate_readings_changes_air_quality_gradually_between_events() -> None:
    readings = generate_readings(seed=42)
    air_quality = _readings_by_sensor_id(readings, "air_quality-000")
    pm25_values = [reading.payload.pm2_5 for reading in air_quality if isinstance(reading.payload, AirQualityPayload)]
    diffs = [abs(pm25_values[index] - pm25_values[index - 1]) for index in range(1, len(pm25_values))]
    sorted_diffs = sorted(diffs)

    assert sorted_diffs[len(sorted_diffs) // 2] < 3.5
    assert sorted_diffs[int(len(sorted_diffs) * 0.95)] < 12.0


def test_generate_readings_keeps_energy_cumulative_monotonic() -> None:
    readings = generate_readings(seed=42)
    energy_readings = [reading for reading in readings if reading.metadata.sensor_type == SensorType.ENERGY_METER]
    cumulative_by_sensor: dict[str, list[float]] = defaultdict(list)

    for reading in energy_readings:
        assert isinstance(reading.payload, EnergyMeterPayload)
        cumulative_by_sensor[reading.metadata.sensor_id].append(reading.payload.cumulative_kwh)

    for values in cumulative_by_sensor.values():
        assert values == sorted(values)


def test_generate_readings_keeps_traffic_light_state_stable_for_multiple_steps() -> None:
    readings = generate_readings(seed=42)
    traffic_light = _readings_by_sensor_id(readings, "traffic_light-000")
    states = [reading.payload.state for reading in traffic_light if isinstance(reading.payload, TrafficLightPayload)]
    transitions = sum(states[index] != states[index - 1] for index in range(1, len(states)))

    assert transitions < len(states) // 2


def test_generate_readings_keeps_timestamps_monotonic_per_sensor() -> None:
    readings = generate_readings(seed=42)
    timestamps_by_sensor: dict[str, list[datetime]] = defaultdict(list)

    for reading in readings:
        timestamps_by_sensor[reading.metadata.sensor_id].append(reading.metadata.timestamp)

    for timestamps in timestamps_by_sensor.values():
        assert timestamps == sorted(timestamps)


def test_write_csv_files_interleaves_sensor_ids_by_timestamp() -> None:
    _cleanup_output_dir()
    readings = generate_readings(seed=42)
    write_csv_files(readings, _OUTPUT_DIR)

    car_park_rows = (_OUTPUT_DIR / "car_parks.csv").read_text(encoding="utf-8").splitlines()[1:6]
    sensor_ids = [row.split(",", 1)[0] for row in car_park_rows]

    assert sensor_ids == [
        "car_park-000",
        "car_park-001",
        "car_park-002",
        "car_park-003",
        "car_park-004",
    ]

    _cleanup_output_dir()


def test_csv_round_trip_restores_same_sensor_metadata() -> None:
    _cleanup_output_dir()
    readings = generate_readings(seed=42)
    paths = write_csv_files(readings, _OUTPUT_DIR)

    for sensor_type, path in paths.items():
        restored = read_csv_file(path)
        original = sorted(
            (reading for reading in readings if reading.metadata.sensor_type == sensor_type),
            key=lambda reading: (reading.metadata.timestamp, reading.metadata.sensor_id),
        )
        restored_sorted = sorted(
            restored,
            key=lambda reading: (reading.metadata.timestamp, reading.metadata.sensor_id),
        )

        assert len(restored_sorted) == len(original)
        for source, recovered in zip(original, restored_sorted):
            assert source.metadata.sensor_id == recovered.metadata.sensor_id
            assert source.metadata.sensor_type == recovered.metadata.sensor_type
            assert source.payload.model_dump() == recovered.payload.model_dump()

    _cleanup_output_dir()


def test_generate_readings_is_deterministic_for_same_seed() -> None:
    first = generate_readings(seed=42)
    second = generate_readings(seed=42)

    assert len(first) == len(second)
    for left, right in zip(first, second):
        assert left.metadata.sensor_id == right.metadata.sensor_id
        assert left.metadata.sensor_type == right.metadata.sensor_type
        assert left.payload.model_dump() == right.payload.model_dump()


def test_generate_readings_differs_for_different_seeds() -> None:
    first = generate_readings(seed=42)
    second = generate_readings(seed=99)

    first_payloads = [reading.payload.model_dump() for reading in first[:10]]
    second_payloads = [reading.payload.model_dump() for reading in second[:10]]

    assert first_payloads != second_payloads
