from typing import Literal

from pydantic import BaseModel, Field


class EnergyMeterPayload(BaseModel):
    """Дані лічильника електроенергії технологічної системи."""

    kind: Literal["energy_meter"] = "energy_meter"

    power_kw: float = Field(description="Миттєва активна потужність, кВт.")
    voltage_v: float = Field(gt=0.0, description="Напруга, В.")
    current_a: float = Field(ge=0.0, description="Струм, А.")
    cumulative_kwh: float = Field(ge=0.0, description="Накопичена енергія з моменту встановлення, кВт·год.")
    power_factor: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Коефіцієнт потужності (cos φ).",
    )
