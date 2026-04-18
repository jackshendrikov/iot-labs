from typing import Literal

from pydantic import BaseModel, Field


class AirQualityPayload(BaseModel):
    """Дані сенсора якості повітря (відкриті дані EEA / SaveEcoBot)."""

    kind: Literal["air_quality"] = "air_quality"

    pm2_5: float = Field(ge=0.0, description="Концентрація PM2.5, мкг/м³.")
    pm10: float = Field(ge=0.0, description="Концентрація PM10, мкг/м³.")
    no2: float = Field(ge=0.0, description="Концентрація NO₂, мкг/м³.")
    o3: float | None = Field(default=None, ge=0.0, description="Концентрація O₃, мкг/м³.")
    temperature_c: float = Field(description="Температура повітря, °C.")
    humidity_percent: float = Field(ge=0.0, le=100.0, description="Відносна вологість, %.")
    pressure_hpa: float | None = Field(default=None, gt=0.0, description="Атмосферний тиск, гПа.")
