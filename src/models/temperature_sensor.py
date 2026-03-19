from pydantic import BaseModel

from src.models.gps import Gps


class TemperatureSensor(BaseModel):
    temperature: float
    humidity: float
    gps: Gps
