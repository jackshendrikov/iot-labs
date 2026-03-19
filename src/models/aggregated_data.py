from datetime import datetime, timezone

from pydantic import BaseModel, Field

from src.models.accelerometer import Accelerometer
from src.models.gps import Gps
from src.models.temperature_sensor import TemperatureSensor


class AggregatedData(BaseModel):
    accelerometer: Accelerometer
    gps: Gps
    temperature_sensor: TemperatureSensor | None = None
    time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
