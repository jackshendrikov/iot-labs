from typing import Annotated, Union

from pydantic import Field

from src.models.payloads.air_quality import AirQualityPayload
from src.models.payloads.car_park import CarParkPayload
from src.models.payloads.energy_meter import EnergyMeterPayload
from src.models.payloads.traffic_light import TrafficLightPayload, TrafficLightState

SensorPayload = Annotated[
    Union[
        CarParkPayload,
        TrafficLightPayload,
        AirQualityPayload,
        EnergyMeterPayload,
    ],
    Field(discriminator="kind"),
]

__all__ = [
    "AirQualityPayload",
    "CarParkPayload",
    "EnergyMeterPayload",
    "SensorPayload",
    "TrafficLightPayload",
    "TrafficLightState",
]
