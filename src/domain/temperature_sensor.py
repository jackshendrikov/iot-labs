from pydantic import BaseModel

from src.domain import Gps


class TemperatureSensor(BaseModel):
    temperature: float
    humidity: float
    gps: Gps
