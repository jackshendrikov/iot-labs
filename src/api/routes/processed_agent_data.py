from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_db
from src.api.ws_manager import manager
from src.core.logger import logger
from src.models import ProcessedAgentData, ProcessedAgentDataInDB
from src.repository.processed_agent_data import ProcessedAgentDataRepository

router = APIRouter(prefix="/processed_agent_data", tags=["Processed Agent Data"])


@router.post("/", response_model=list[ProcessedAgentDataInDB], status_code=201)
async def create_processed_agent_data(
    data: list[ProcessedAgentData],
    db: AsyncSession = Depends(get_db),
) -> list[ProcessedAgentDataInDB]:
    """Зберігає список оброблених записів та транслює їх підписникам WebSocket."""
    repo = ProcessedAgentDataRepository(db)

    try:
        items = await repo.create_batch(data)
        await db.commit()
    except Exception:
        await db.rollback()
        logger.exception("Помилка під час створення batch записів processed_agent_data")
        raise

    result = [ProcessedAgentDataInDB.model_validate(item) for item in items]

    for record in result:
        await manager.broadcast(record.model_dump_json())

    return result


@router.get("/", response_model=list[ProcessedAgentDataInDB])
async def list_processed_agent_data(
    db: AsyncSession = Depends(get_db),
) -> list[ProcessedAgentDataInDB]:
    """Повертає список усіх збережених записів."""
    repo = ProcessedAgentDataRepository(db)
    items = await repo.get_all()
    return [ProcessedAgentDataInDB.model_validate(item) for item in items]


@router.get("/{record_id}", response_model=ProcessedAgentDataInDB)
async def read_processed_agent_data(
    record_id: int,
    db: AsyncSession = Depends(get_db),
) -> ProcessedAgentDataInDB:
    """Повертає один запис за його id."""
    repo = ProcessedAgentDataRepository(db)
    item = await repo.get_by_id(record_id)
    if not item:
        raise HTTPException(status_code=404, detail=f"Запис з id={record_id} не знайдено")
    return ProcessedAgentDataInDB.model_validate(item)


@router.put("/{record_id}", response_model=ProcessedAgentDataInDB)
async def update_processed_agent_data(
    record_id: int,
    data: ProcessedAgentData,
    db: AsyncSession = Depends(get_db),
) -> ProcessedAgentDataInDB:
    """Оновлює наявний запис за його id."""
    repo = ProcessedAgentDataRepository(db)

    try:
        item = await repo.update(record_id, data)
        if not item:
            await db.rollback()
            raise HTTPException(status_code=404, detail=f"Запис з id={record_id} не знайдено")

        await db.commit()
    except HTTPException:
        raise
    except Exception:
        await db.rollback()
        logger.exception("Помилка під час оновлення запису processed_agent_data")
        raise

    return ProcessedAgentDataInDB.model_validate(item)


@router.delete("/{record_id}", response_model=ProcessedAgentDataInDB)
async def delete_processed_agent_data(
    record_id: int,
    db: AsyncSession = Depends(get_db),
) -> ProcessedAgentDataInDB:
    """Видаляє запис за його id та повертає видалений об'єкт."""
    repo = ProcessedAgentDataRepository(db)

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
        logger.exception("Помилка під час видалення запису processed_agent_data")
        raise

    return ProcessedAgentDataInDB.model_validate(item)
