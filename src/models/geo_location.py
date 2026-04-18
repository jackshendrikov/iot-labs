from pydantic import BaseModel, Field


class GeoLocation(BaseModel):
    """Географічна точка у форматі WGS-84."""

    latitude: float = Field(ge=-90.0, le=90.0)
    longitude: float = Field(ge=-180.0, le=180.0)
