"""Генератор синтетичних показань для нових сенсорних об'єктів.

Значення параметрів узгоджені з відкритими датасетами:
- паркомісця: SFMTA SFpark (total/occupied spots, середня тривалість парковки);
- світлофори: типові цикли 60–120 с, Київська відкрита карта світлофорів;
- якість повітря: EEA AQ e-reporting / SaveEcoBot (PM2.5, PM10, NO₂, O₃, T, RH, P);
- лічильники енергії: телеметрія промислових smart-meter'ів (P, U, I, kWh, PF).
"""

import csv
import json
import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

from src.models import (
    AirQualityPayload,
    CarParkPayload,
    EnergyMeterPayload,
    GeoLocation,
    SensorReading,
    SensorType,
    TrafficLightPayload,
    TrafficLightState,
)

# Центр Києва — базова точка для розсіювання штучних сенсорів.
_KYIV_CENTER = (50.4501, 30.5234)
_JITTER_DEG = 0.05  # ~±5.5 км


@dataclass(frozen=True)
class _ObjectSpec:
    """Параметри групи сенсорних об'єктів для генерації."""

    sensor_type: SensorType
    count: int
    samples_per_sensor: int
    build_payload_factory: Callable[[random.Random], Callable[[random.Random, int], dict]]
    csv_filename: str


def _random_location(rng: random.Random) -> GeoLocation:
    lat = _KYIV_CENTER[0] + rng.uniform(-_JITTER_DEG, _JITTER_DEG)
    lon = _KYIV_CENTER[1] + rng.uniform(-_JITTER_DEG, _JITTER_DEG)
    return GeoLocation(latitude=lat, longitude=lon)


def _car_park_factory(sensor_rng: random.Random) -> Callable[[random.Random, int], dict]:
    # Сталі per-sensor параметри: ємність фіксована на час життя сенсора.
    total = sensor_rng.choice([30, 60, 120, 200, 350])

    def _build(rng: random.Random, step: int) -> dict:
        # Проста добова модель зайнятості: пік близько 13:00.
        hour = step % 24
        base_rate = 0.25 + 0.55 * (1 - abs(13 - hour) / 13)
        rate = max(0.0, min(1.0, base_rate + rng.uniform(-0.1, 0.1)))
        occupied = int(total * rate)
        stay = round(rng.uniform(20.0, 180.0), 1)
        return CarParkPayload(
            total_spots=total,
            occupied_spots=occupied,
            avg_stay_minutes=stay,
        ).model_dump(mode="json")

    return _build


def _traffic_light_factory(sensor_rng: random.Random) -> Callable[[random.Random, int], dict]:
    cycle = sensor_rng.choice([60, 75, 90, 120])

    def _build(rng: random.Random, step: int) -> dict:
        phase = step % 4
        state = {
            0: TrafficLightState.RED,
            1: TrafficLightState.GREEN,
            2: TrafficLightState.YELLOW,
            3: TrafficLightState.RED,
        }[phase]
        queue = max(0, int(rng.gauss(5, 3)))
        ped = rng.random() < 0.15
        return TrafficLightPayload(
            state=state,
            cycle_seconds=cycle,
            queue_length=queue,
            pedestrian_request=ped,
        ).model_dump(mode="json")

    return _build


def _air_quality_factory(_: random.Random) -> Callable[[random.Random, int], dict]:
    def _build(rng: random.Random, step: int) -> dict:
        pm25 = max(0.0, rng.gauss(18, 8))
        pm10 = pm25 + max(0.0, rng.gauss(10, 5))
        no2 = max(0.0, rng.gauss(25, 10))
        o3 = max(0.0, rng.gauss(60, 15))
        temp = rng.gauss(12, 6)
        rh = max(20.0, min(100.0, rng.gauss(65, 12)))
        pressure = rng.gauss(1013, 6)
        return AirQualityPayload(
            pm2_5=round(pm25, 2),
            pm10=round(pm10, 2),
            no2=round(no2, 2),
            o3=round(o3, 2),
            temperature_c=round(temp, 2),
            humidity_percent=round(rh, 1),
            pressure_hpa=round(pressure, 1),
        ).model_dump(mode="json")

    return _build


def _energy_meter_factory(_: random.Random) -> Callable[[random.Random, int], dict]:
    # Накопичувач енергії монотонно зростає в межах одного сенсора.
    cumulative_state = {"value": 0.0}

    def _build(rng: random.Random, step: int) -> dict:
        voltage = rng.gauss(230, 2.5)
        current = max(0.0, rng.gauss(18, 5))
        power = round(voltage * current / 1000.0, 3)
        cumulative_state["value"] += power * 0.25  # 15-хвилинні інтервали
        pf = round(rng.uniform(0.85, 0.99), 3)
        return EnergyMeterPayload(
            power_kw=power,
            voltage_v=round(voltage, 2),
            current_a=round(current, 2),
            cumulative_kwh=round(cumulative_state["value"], 3),
            power_factor=pf,
        ).model_dump(mode="json")

    return _build


_SPECS: tuple[_ObjectSpec, ...] = (
    _ObjectSpec(
        SensorType.CAR_PARK,
        count=5,
        samples_per_sensor=24,
        build_payload_factory=_car_park_factory,
        csv_filename="car_parks.csv",
    ),
    _ObjectSpec(
        SensorType.TRAFFIC_LIGHT,
        count=8,
        samples_per_sensor=20,
        build_payload_factory=_traffic_light_factory,
        csv_filename="traffic_lights.csv",
    ),
    _ObjectSpec(
        SensorType.AIR_QUALITY,
        count=4,
        samples_per_sensor=24,
        build_payload_factory=_air_quality_factory,
        csv_filename="air_quality.csv",
    ),
    _ObjectSpec(
        SensorType.ENERGY_METER,
        count=3,
        samples_per_sensor=24,
        build_payload_factory=_energy_meter_factory,
        csv_filename="energy_meters.csv",
    ),
)

_CSV_FIELDS = ("sensor_id", "sensor_type", "latitude", "longitude", "timestamp", "payload")


def generate_readings(seed: int = 42) -> list[SensorReading]:
    """Генерує перелік SensorReading-ів для всіх типів сенсорів."""
    rng = random.Random(seed)
    start = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)

    readings: list[SensorReading] = []
    for spec in _SPECS:
        for i in range(spec.count):
            sensor_id = f"{spec.sensor_type.value}-{i:03d}"
            location = _random_location(rng)
            build_payload = spec.build_payload_factory(rng)
            for step in range(spec.samples_per_sensor):
                payload_dict = build_payload(rng, step)
                timestamp = start - timedelta(hours=spec.samples_per_sensor - step)
                reading = SensorReading.model_validate(
                    {
                        "metadata": {
                            "sensor_id": sensor_id,
                            "sensor_type": spec.sensor_type,
                            "location": location.model_dump(),
                            "timestamp": timestamp.isoformat(),
                        },
                        "payload": payload_dict,
                    }
                )
                readings.append(reading)
    return readings


def write_csv_files(readings: list[SensorReading], output_dir: Path) -> dict[SensorType, Path]:
    """Зберігає показання у CSV-файлах, по одному на кожен тип сенсора."""
    output_dir.mkdir(parents=True, exist_ok=True)
    by_type: dict[SensorType, list[SensorReading]] = {}
    for reading in readings:
        by_type.setdefault(reading.metadata.sensor_type, []).append(reading)

    written: dict[SensorType, Path] = {}
    for spec in _SPECS:
        rows = by_type.get(spec.sensor_type, [])
        if not rows:
            continue
        path = output_dir / spec.csv_filename
        with path.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=_CSV_FIELDS)
            writer.writeheader()
            for reading in rows:
                writer.writerow(
                    {
                        "sensor_id": reading.metadata.sensor_id,
                        "sensor_type": reading.metadata.sensor_type.value,
                        "latitude": reading.metadata.location.latitude,
                        "longitude": reading.metadata.location.longitude,
                        "timestamp": reading.metadata.timestamp.isoformat(),
                        "payload": json.dumps(reading.payload.model_dump(mode="json")),
                    }
                )
        written[spec.sensor_type] = path
    return written


def read_csv_file(path: Path) -> list[SensorReading]:
    """Відновлює список SensorReading-ів зі згенерованого CSV-файлу."""
    readings: list[SensorReading] = []
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            readings.append(
                SensorReading.model_validate(
                    {
                        "metadata": {
                            "sensor_id": row["sensor_id"],
                            "sensor_type": row["sensor_type"],
                            "location": {
                                "latitude": float(row["latitude"]),
                                "longitude": float(row["longitude"]),
                            },
                            "timestamp": row["timestamp"],
                        },
                        "payload": json.loads(row["payload"]),
                    }
                )
            )
    return readings
