from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_db
from src.api.metrics import ANOMALY_FLAGS_TOTAL, SENSOR_READINGS_TOTAL
from src.api.ws_manager import sensors_manager
from src.core.logger import logger
from src.models import SensorReading, SensorReadingInDB, SensorType
from src.repository.sensor_reading import SensorReadingRepository

router = APIRouter(prefix="/sensor_readings", tags=["Sensor Readings"])


@router.post("/", response_model=list[SensorReadingInDB], status_code=201)
async def create_sensor_readings(
    data: list[SensorReading],
    db: AsyncSession = Depends(get_db),
) -> list[SensorReadingInDB]:
    """Зберігає пакет універсальних показань сенсорів та транслює в WebSocket."""
    repo = SensorReadingRepository(db)

    try:
        items = await repo.create_batch(data)
        await db.commit()
    except Exception:
        await db.rollback()
        logger.exception("Помилка під час створення batch показань сенсорів")
        raise

    result = [SensorReadingInDB.model_validate(item) for item in items]
    for record in result:
        SENSOR_READINGS_TOTAL.labels(sensor_type=record.sensor_type.value).inc()
        for flag in record.anomaly_flags:
            ANOMALY_FLAGS_TOTAL.labels(sensor_type=record.sensor_type.value, flag=flag).inc()
        await sensors_manager.broadcast(record.model_dump_json())

    return result


@router.get("/", response_model=list[SensorReadingInDB])
async def list_sensor_readings(
    sensor_type: SensorType | None = Query(default=None, description="Фільтр за типом сенсора."),
    sensor_id: str | None = Query(default=None, description="Фільтр за ідентифікатором сенсора."),
    limit: int = Query(default=1000, ge=1, le=10_000),
    db: AsyncSession = Depends(get_db),
) -> list[SensorReadingInDB]:
    """Повертає показання сенсорів із опційною фільтрацією."""
    repo = SensorReadingRepository(db)
    items = await repo.list_filtered(sensor_type=sensor_type, sensor_id=sensor_id, limit=limit)
    return [SensorReadingInDB.model_validate(item) for item in items]


@router.get("/{record_id}", response_model=SensorReadingInDB)
async def read_sensor_reading(
    record_id: int,
    db: AsyncSession = Depends(get_db),
) -> SensorReadingInDB:
    """Повертає одне показання сенсора за його id."""
    repo = SensorReadingRepository(db)
    item = await repo.get_by_id(record_id)
    if not item:
        raise HTTPException(status_code=404, detail=f"Запис з id={record_id} не знайдено")
    return SensorReadingInDB.model_validate(item)


@router.delete("/{record_id}", response_model=SensorReadingInDB)
async def delete_sensor_reading(
    record_id: int,
    db: AsyncSession = Depends(get_db),
) -> SensorReadingInDB:
    """Видаляє показання сенсора за id."""
    repo = SensorReadingRepository(db)

    try:
        item = await repo.delete(record_id)
        if not item:
            await db.rollback()
            raise HTTPException(status_code=404, detail=f"Запис з id={record_id} не знайдено")

        await db.commit()
    except HTTPException:
        raise
    except Exception:
        await db.rollback()
        logger.exception("Помилка під час видалення показання сенсора")
        raise

    return SensorReadingInDB.model_validate(item)
