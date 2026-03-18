from pydantic import BaseModel


class Gps(BaseModel):
    longitude: float
    latitude: float
