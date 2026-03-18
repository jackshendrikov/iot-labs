from datetime import datetime, timezone

from pydantic import BaseModel, Field

from src.domain import Accelerometer, Gps
from src.domain.temperature_sensor import TemperatureSensor


class AggregatedData(BaseModel):
    accelerometer: Accelerometer
    gps: Gps
    temperature_sensor: TemperatureSensor | None = None
    time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
