from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_db
from src.db.orm_models import NetworkAnomalyORM
from src.models.network_anomaly import NetworkAnomalyInDB

router = APIRouter(prefix="/network_anomalies", tags=["Network Anomalies"])


@router.get("/", response_model=list[NetworkAnomalyInDB])
async def list_network_anomalies(
    metric: str | None = Query(default=None, description="Фільтр за назвою метрики."),
    severity: str | None = Query(default=None, description="Фільтр за серйозністю: minor|major|critical."),
    limit: int = Query(default=200, ge=1, le=10_000),
    db: AsyncSession = Depends(get_db),
) -> list[NetworkAnomalyInDB]:
    """Повертає перелік зафіксованих мережевих аномалій."""
    stmt = select(NetworkAnomalyORM)
    if metric is not None:
        stmt = stmt.where(NetworkAnomalyORM.metric == metric)
    if severity is not None:
        stmt = stmt.where(NetworkAnomalyORM.severity == severity)
    stmt = stmt.order_by(NetworkAnomalyORM.timestamp.desc()).limit(limit)

    result = await db.execute(stmt)
    rows = result.scalars().all()
    return [NetworkAnomalyInDB.model_validate(item) for item in rows]
