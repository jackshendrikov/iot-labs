from datetime import datetime

from pydantic import BaseModel, ConfigDict


class NetworkAnomalyInDB(BaseModel):
    id: int
    timestamp: datetime
    metric: str
    value: float
    baseline_mean: float
    baseline_std: float
    zscore: float
    severity: str

    model_config = ConfigDict(from_attributes=True)
