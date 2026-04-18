from enum import StrEnum


class SensorType(StrEnum):
    """Тип сенсорного об'єкта, що підтримується універсальною структурою."""

    CAR_PARK = "car_park"
    TRAFFIC_LIGHT = "traffic_light"
    AIR_QUALITY = "air_quality"
    ENERGY_METER = "energy_meter"
