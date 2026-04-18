from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


class TrafficLightState(StrEnum):
    """Поточний стан світлофора."""

    RED = "red"
    YELLOW = "yellow"
    GREEN = "green"
    FLASHING_YELLOW = "flashing_yellow"
    OFF = "off"


class TrafficLightPayload(BaseModel):
    """Дані сенсора світлофора: стан, цикл та довжина черги."""

    kind: Literal["traffic_light"] = "traffic_light"

    state: TrafficLightState
    cycle_seconds: int = Field(gt=0, description="Тривалість повного циклу у секундах.")
    queue_length: int = Field(
        ge=0,
        description="Оцінена довжина черги транспорту (кількість ТЗ).",
    )
    pedestrian_request: bool = Field(
        default=False,
        description="Ознака активованого виклику пішохідної фази.",
    )
