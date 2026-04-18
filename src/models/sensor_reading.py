from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.models.geo_location import GeoLocation
from src.models.payloads import SensorPayload
from src.models.sensor_type import SensorType


class SensorMetadata(BaseModel):
    """Спільні метадані будь-якого сенсора універсальної структури."""

    sensor_id: str = Field(min_length=1, max_length=128, description="Унікальний ідентифікатор пристрою.")
    sensor_type: SensorType
    location: GeoLocation
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SensorReading(BaseModel):
    """Універсальний запис сенсора: метадані + типоспецифічний payload."""

    metadata: SensorMetadata
    payload: SensorPayload

    @model_validator(mode="after")
    def _check_sensor_type_matches_payload(self) -> "SensorReading":
        if self.metadata.sensor_type.value != self.payload.kind:
            raise ValueError("metadata.sensor_type має відповідати payload.kind")
        return self


class SensorReadingInDB(BaseModel):
    """Вихідне представлення запису з бази даних."""

    id: int
    sensor_id: str
    sensor_type: SensorType
    latitude: float
    longitude: float
    timestamp: datetime
    payload: dict

    model_config = ConfigDict(from_attributes=True)
