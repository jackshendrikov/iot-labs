from pydantic import BaseModel


class Accelerometer(BaseModel):
    x: float
    y: float
    z: float
