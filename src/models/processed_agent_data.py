from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from src.models.aggregated_data import AggregatedData


class RoadState(StrEnum):
    GOOD = "good"
    WARNING = "warning"
    BAD = "bad"


class ProcessedAgentData(BaseModel):
    road_state: RoadState
    agent_data: AggregatedData


class ProcessedAgentDataInDB(BaseModel):
    id: int
    road_state: RoadState
    x: float
    y: float
    z: float
    latitude: float
    longitude: float
    timestamp: datetime

    model_config = ConfigDict(from_attributes=True)
