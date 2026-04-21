"""Генератор синтетичних показань для нових сенсорних об'єктів.

Значення параметрів узгоджені з відкритими датасетами:
- паркомісця: SFMTA SFpark (total/occupied spots, середня тривалість парковки);
- світлофори: типові цикли 60–120 с, Київська відкрита карта світлофорів;
- якість повітря: EEA AQ e-reporting / SaveEcoBot (PM2.5, PM10, NO₂, O₃, T, RH, P);
- лічильники енергії: телеметрія промислових smart-meter'ів (P, U, I, kWh, PF).
"""

import csv
import json
import math
import random
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

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

_KYIV_CENTER = (50.4501, 30.5234)
_JITTER_DEG = 0.05
_CSV_FIELDS = ("sensor_id", "sensor_type", "latitude", "longitude", "timestamp", "payload")

type _PayloadDict = dict[str, object]
type _PayloadFactory = Callable[[random.Random, int], _PayloadDict]
type _PayloadFactoryBuilder = Callable[[random.Random], _PayloadFactory]


@dataclass(frozen=True)
class _ObjectSpec:
    sensor_type: SensorType
    count: int
    samples_per_sensor: int
    build_payload_factory: _PayloadFactoryBuilder
    csv_filename: str


def _random_location(rng: random.Random) -> GeoLocation:
    """Повертає випадкову геолокацію поблизу центру Києва."""
    latitude = _KYIV_CENTER[0] + rng.uniform(-_JITTER_DEG, _JITTER_DEG)
    longitude = _KYIV_CENTER[1] + rng.uniform(-_JITTER_DEG, _JITTER_DEG)
    return GeoLocation(latitude=latitude, longitude=longitude)


def _diurnal(step: int, phase: int, period: int = 96) -> float:
    """Повертає плавний добовий цикл у діапазоні `0..1`."""
    angle = 2 * math.pi * ((step + phase) % period) / period
    return 0.5 + 0.5 * math.sin(angle - math.pi / 2)


def _ou(current: float, mean: float, theta: float, noise: float, rng: random.Random) -> float:
    """Виконує один крок OU-процесу з поверненням до середнього."""
    return current + theta * (mean - current) + rng.uniform(-noise, noise)


def _car_park_factory(sensor_rng: random.Random) -> _PayloadFactory:
    total = sensor_rng.choice([30, 60, 120, 200, 350])
    phase = sensor_rng.randint(0, 95)
    overcrowded_at = sensor_rng.randint(10, 30)
    long_stay_at = sensor_rng.randint(24, 50)
    state = {"rate": sensor_rng.uniform(0.30, 0.55), "stay": 45.0, "oc": 0.0, "stay_boost": 0.0}

    def _build(rng: random.Random, step: int) -> _PayloadDict:
        base_rate = 0.20 + 0.58 * _diurnal(step, phase)
        state["oc"] *= 0.80
        state["stay_boost"] *= 0.82
        state["rate"] = max(0.02, min(0.98, _ou(state["rate"], base_rate + state["oc"], 0.18, 0.015, rng)))
        if step >= overcrowded_at and (step - overcrowded_at) % 48 == 0:
            state["oc"] = max(state["oc"], 0.30)
            state["rate"] = min(0.98, state["rate"] + state["oc"])
        if step >= long_stay_at and (step - long_stay_at) % 72 == 0:
            state["stay_boost"] = 260.0
            state["stay"] = max(state["stay"], 250.0)
        state["stay"] = max(
            10.0,
            _ou(state["stay"], 35.0 + state["rate"] * 80.0 + state["stay_boost"], 0.20, 3.0, rng),
        )
        occupied_spots = int(total * state["rate"])
        return CarParkPayload(
            total_spots=total,
            occupied_spots=occupied_spots,
            avg_stay_minutes=round(state["stay"], 1),
        ).model_dump(mode="json")

    return _build


def _traffic_light_factory(sensor_rng: random.Random) -> _PayloadFactory:
    cycle = sensor_rng.choice([60, 75, 90, 120])
    phase_offset = sensor_rng.randint(0, 3)
    phase_span = {60: 3, 75: 4, 90: 5, 120: 6}[cycle]
    congested_at = sensor_rng.randint(12, 24)
    gridlock_at = sensor_rng.randint(40, 60)
    off_at = sensor_rng.randint(90, 140)
    state = {"queue": float(sensor_rng.randint(0, 4)), "extra": 0.0}

    def _build(rng: random.Random, step: int) -> _PayloadDict:
        phase = ((step // phase_span) + phase_offset) % 4
        light = {
            0: TrafficLightState.RED,
            1: TrafficLightState.GREEN,
            2: TrafficLightState.YELLOW,
            3: TrafficLightState.RED,
        }[phase]
        target_queue = 7.0 if light == TrafficLightState.RED else (2.5 if light == TrafficLightState.YELLOW else 1.0)
        state["extra"] *= 0.78
        if step >= congested_at and (step - congested_at) % 36 == 0:
            state["extra"] = max(state["extra"], rng.uniform(6.0, 8.0))
        if step >= gridlock_at and (step - gridlock_at) % 84 == 0:
            state["extra"] = max(state["extra"], 18.0)
            state["queue"] = max(state["queue"], 21.0)
        state["queue"] = max(0.0, _ou(state["queue"], target_queue + state["extra"], 0.28, 0.5, rng))
        queue_length = int(round(state["queue"]))
        if step >= off_at and (step - off_at) % 144 == 0:
            light = TrafficLightState.OFF

        return TrafficLightPayload(
            state=light,
            cycle_seconds=cycle,
            queue_length=queue_length,
            pedestrian_request=rng.random() < 0.15,
        ).model_dump(mode="json")

    return _build


def _air_quality_factory(sensor_rng: random.Random) -> _PayloadFactory:
    phase = sensor_rng.randint(0, 95)
    pm_unhealthy_at = sensor_rng.randint(15, 30)
    pm_very_unhealthy_at = sensor_rng.randint(50, 70)
    no2_at = sensor_rng.randint(70, 100)
    o3_at = sensor_rng.randint(90, 130)
    state = {"pm25": 14.0, "pm10": 24.0, "no2": 22.0, "o3": 58.0, "temp": 12.0, "rh": 64.0, "pressure": 1013.0}
    plume = {"pm25": 0.0, "pm10": 0.0, "no2": 0.0, "o3": 0.0}

    def _build(rng: random.Random, step: int) -> _PayloadDict:
        cycle = _diurnal(step, phase)
        for metric in plume:
            plume[metric] *= 0.83

        if step >= pm_unhealthy_at and (step - pm_unhealthy_at) % 72 == 0:
            plume["pm25"] = max(plume["pm25"], rng.uniform(22.0, 26.0))
            plume["pm10"] = max(plume["pm10"], rng.uniform(28.0, 34.0))
            state["pm25"] = max(state["pm25"], rng.uniform(36.0, 42.0))
        if step >= pm_very_unhealthy_at and (step - pm_very_unhealthy_at) % 144 == 0:
            plume["pm25"] = max(plume["pm25"], rng.uniform(42.0, 48.0))
            plume["pm10"] = max(plume["pm10"], rng.uniform(52.0, 60.0))
            state["pm25"] = max(state["pm25"], rng.uniform(57.0, 63.0))
        if step >= no2_at and (step - no2_at) % 144 == 0:
            plume["no2"] = max(plume["no2"], rng.uniform(40.0, 50.0))
            state["no2"] = max(state["no2"], rng.uniform(61.0, 68.0))
        if step >= o3_at and (step - o3_at) % 192 == 0:
            plume["o3"] = max(plume["o3"], rng.uniform(45.0, 55.0))
            state["o3"] = max(state["o3"], rng.uniform(102.0, 110.0))

        state["pm25"] = max(3.0, _ou(state["pm25"], 11.0 + cycle * 8.0 + plume["pm25"], 0.12, 0.8, rng))
        state["pm10"] = max(
            state["pm25"] + 3.0,
            _ou(state["pm10"], state["pm25"] + 8.0 + plume["pm10"], 0.14, 1.0, rng),
        )
        state["no2"] = max(5.0, _ou(state["no2"], 18.0 + cycle * 10.0 + plume["no2"], 0.12, 1.2, rng))
        state["o3"] = max(15.0, _ou(state["o3"], 48.0 + (1 - cycle) * 14.0 + plume["o3"], 0.10, 1.5, rng))
        state["temp"] = _ou(state["temp"], 10.0 + cycle * 8.0, 0.18, 0.4, rng)
        state["rh"] = max(25.0, min(100.0, _ou(state["rh"], 72.0 - cycle * 12.0, 0.12, 1.2, rng)))
        state["pressure"] = _ou(state["pressure"], 1013.0, 0.05, 0.4, rng)

        return AirQualityPayload(
            pm2_5=round(state["pm25"], 2),
            pm10=round(state["pm10"], 2),
            no2=round(state["no2"], 2),
            o3=round(state["o3"], 2),
            temperature_c=round(state["temp"], 2),
            humidity_percent=round(state["rh"], 1),
            pressure_hpa=round(state["pressure"], 1),
        ).model_dump(mode="json")

    return _build


def _energy_meter_factory(sensor_rng: random.Random) -> _PayloadFactory:
    phase = sensor_rng.randint(0, 95)
    voltage_at = sensor_rng.randint(36, 60)
    overload_at = sensor_rng.randint(72, 100)
    pf_at = sensor_rng.randint(48, 80)
    state = {"voltage": 229.0, "current": 17.5, "pf": 0.94}
    disturbance = {"voltage": 0.0, "current": 0.0, "pf": 0.0}
    cumulative = {"kwh": 0.0}

    def _build(rng: random.Random, step: int) -> _PayloadDict:
        load_mean = 11.0 + 8.0 * (0.5 + 0.5 * (1.0 - abs(18.0 - ((step + phase) % 96) / 4.0) / 18.0))
        disturbance["voltage"] *= 0.78
        disturbance["current"] *= 0.80
        disturbance["pf"] *= 0.80

        if step >= voltage_at and (step - voltage_at) % 96 == 0:
            delta = rng.choice([rng.uniform(-26.0, -24.0), rng.uniform(24.0, 26.0)])
            disturbance["voltage"] = delta
            state["voltage"] = 230.0 + delta
        if step >= overload_at and (step - overload_at) % 144 == 0:
            disturbance["current"] = rng.uniform(16.0, 20.0)
            state["current"] = load_mean + disturbance["current"]
        if step >= pf_at and (step - pf_at) % 120 == 0:
            disturbance["pf"] = -rng.uniform(0.07, 0.10)
            state["pf"] = 0.94 + disturbance["pf"]

        state["voltage"] = _ou(state["voltage"], 230.0 + disturbance["voltage"], 0.18, 0.5, rng)
        state["current"] = max(2.0, _ou(state["current"], load_mean + disturbance["current"], 0.22, 0.4, rng))
        state["pf"] = min(0.99, max(0.78, _ou(state["pf"], 0.94 + disturbance["pf"], 0.18, 0.003, rng)))

        power_kw = round(state["voltage"] * state["current"] / 1000.0, 3)
        cumulative["kwh"] += power_kw * 0.25

        return EnergyMeterPayload(
            power_kw=power_kw,
            voltage_v=round(state["voltage"], 2),
            current_a=round(state["current"], 2),
            cumulative_kwh=round(cumulative["kwh"], 3),
            power_factor=round(state["pf"], 3),
        ).model_dump(mode="json")

    return _build


_SPECS: tuple[_ObjectSpec, ...] = (
    _ObjectSpec(
        SensorType.CAR_PARK,
        count=5,
        samples_per_sensor=192,
        build_payload_factory=_car_park_factory,
        csv_filename="car_parks.csv",
    ),
    _ObjectSpec(
        SensorType.TRAFFIC_LIGHT,
        count=8,
        samples_per_sensor=192,
        build_payload_factory=_traffic_light_factory,
        csv_filename="traffic_lights.csv",
    ),
    _ObjectSpec(
        SensorType.AIR_QUALITY,
        count=4,
        samples_per_sensor=192,
        build_payload_factory=_air_quality_factory,
        csv_filename="air_quality.csv",
    ),
    _ObjectSpec(
        SensorType.ENERGY_METER,
        count=3,
        samples_per_sensor=192,
        build_payload_factory=_energy_meter_factory,
        csv_filename="energy_meters.csv",
    ),
)


def generate_readings(seed: int = 42) -> list[SensorReading]:
    """Генерує повний набір показань для всіх типів сенсорів."""
    rng = random.Random(seed)
    start = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    readings: list[SensorReading] = []

    for spec in _SPECS:
        for index in range(spec.count):
            sensor_id = f"{spec.sensor_type.value}-{index:03d}"
            location = _random_location(rng)
            build_payload = spec.build_payload_factory(rng)

            for step in range(spec.samples_per_sensor):
                timestamp = start - timedelta(minutes=(spec.samples_per_sensor - step) * 15)
                readings.append(
                    SensorReading.model_validate(
                        {
                            "metadata": {
                                "sensor_id": sensor_id,
                                "sensor_type": spec.sensor_type,
                                "location": location.model_dump(),
                                "timestamp": timestamp.isoformat(),
                            },
                            "payload": build_payload(rng, step),
                        }
                    )
                )

    return readings


def write_csv_files(readings: list[SensorReading], output_dir: Path) -> dict[SensorType, Path]:
    """Зберігає показання у CSV-файли, окремо для кожного типу сенсора."""
    output_dir.mkdir(parents=True, exist_ok=True)
    by_type: dict[SensorType, list[SensorReading]] = {}
    for reading in readings:
        by_type.setdefault(reading.metadata.sensor_type, []).append(reading)

    written: dict[SensorType, Path] = {}
    for spec in _SPECS:
        rows = sorted(
            by_type.get(spec.sensor_type, []),
            key=lambda reading: (reading.metadata.timestamp, reading.metadata.sensor_id),
        )
        if not rows:
            continue

        path = output_dir / spec.csv_filename
        with path.open("w", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=_CSV_FIELDS)
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
    """Відновлює список `SensorReading` із раніше згенерованого CSV-файлу."""
    readings: list[SensorReading] = []
    with path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
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
