from collections.abc import Callable

from src.models.payloads import (
    AirQualityPayload,
    CarParkPayload,
    EnergyMeterPayload,
    SensorPayload,
    TrafficLightPayload,
    TrafficLightState,
)

_CAR_PARK_FULL_RATE = 0.95
_CAR_PARK_HIGH_STAY_MINUTES = 240.0

_TRAFFIC_QUEUE_CONGESTED = 10
_TRAFFIC_QUEUE_GRIDLOCK = 20

_PM25_UNHEALTHY = 35.0
_PM25_VERY_UNHEALTHY = 55.0
_PM25_HAZARDOUS = 150.0
_PM10_UNHEALTHY = 150.0
_NO2_HIGH = 60.0
_O3_HIGH = 100.0

_VOLTAGE_MIN = 207.0
_VOLTAGE_MAX = 253.0
_POWER_FACTOR_POOR = 0.90
_POWER_OVERLOAD_KW = 6.0


def _car_park_flags(payload: CarParkPayload) -> list[str]:
    flags: list[str] = []
    if payload.occupancy_rate >= _CAR_PARK_FULL_RATE:
        flags.append("overcrowded")
    if payload.avg_stay_minutes is not None and payload.avg_stay_minutes >= _CAR_PARK_HIGH_STAY_MINUTES:
        flags.append("long_stay")
    return flags


def _traffic_light_flags(payload: TrafficLightPayload) -> list[str]:
    flags: list[str] = []
    if payload.queue_length >= _TRAFFIC_QUEUE_GRIDLOCK:
        flags.append("gridlock")
    elif payload.queue_length >= _TRAFFIC_QUEUE_CONGESTED:
        flags.append("congested")
    if payload.state is TrafficLightState.OFF:
        flags.append("signal_off")
    return flags


def _air_quality_flags(payload: AirQualityPayload) -> list[str]:
    flags: list[str] = []
    if payload.pm2_5 >= _PM25_HAZARDOUS:
        flags.append("hazardous_pm25")
    elif payload.pm2_5 >= _PM25_VERY_UNHEALTHY:
        flags.append("very_unhealthy_pm25")
    elif payload.pm2_5 >= _PM25_UNHEALTHY:
        flags.append("unhealthy_pm25")

    if payload.pm10 >= _PM10_UNHEALTHY:
        flags.append("unhealthy_pm10")
    if payload.no2 >= _NO2_HIGH:
        flags.append("high_no2")
    if payload.o3 is not None and payload.o3 >= _O3_HIGH:
        flags.append("high_o3")
    return flags


def _energy_meter_flags(payload: EnergyMeterPayload) -> list[str]:
    flags: list[str] = []
    if not (_VOLTAGE_MIN <= payload.voltage_v <= _VOLTAGE_MAX):
        flags.append("voltage_out_of_range")
    if payload.power_factor is not None and payload.power_factor < _POWER_FACTOR_POOR:
        flags.append("poor_power_factor")
    if payload.power_kw >= _POWER_OVERLOAD_KW:
        flags.append("power_overload")
    return flags


_RULES: dict[type[object], Callable[..., list[str]]] = {
    CarParkPayload: _car_park_flags,
    TrafficLightPayload: _traffic_light_flags,
    AirQualityPayload: _air_quality_flags,
    EnergyMeterPayload: _energy_meter_flags,
}


def detect_anomaly_flags(payload: SensorPayload) -> list[str]:
    """Повертає список прапорців аномалій для заданого payload."""
    rule = _RULES.get(type(payload))
    if rule is None:
        return []
    return rule(payload)
