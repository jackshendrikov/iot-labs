from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.orm_models import ProcessedAgentDataORM
from src.models.processed_agent_data import ProcessedAgentData


class ProcessedAgentDataRepository:
    """Репозиторій для CRUD-операцій над ProcessedAgentData."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_batch(self, items: list[ProcessedAgentData]) -> list[ProcessedAgentDataORM]:
        """Зберігає список записів у БД та повертає ORM-об'єкти."""
        orm_items = [self._to_orm(item) for item in items]
        self._session.add_all(orm_items)
        await self._session.flush()
        return orm_items

    async def get_by_id(self, record_id: int) -> ProcessedAgentDataORM | None:
        """Повертає запис за його id або None, якщо не знайдено."""
        result = await self._session.execute(select(ProcessedAgentDataORM).where(ProcessedAgentDataORM.id == record_id))
        return result.scalar_one_or_none()

    async def get_all(self) -> list[ProcessedAgentDataORM]:
        """Повертає список усіх записів."""
        result = await self._session.execute(select(ProcessedAgentDataORM))
        return list(result.scalars().all())

    async def update(self, record_id: int, data: ProcessedAgentData) -> ProcessedAgentDataORM | None:
        """Оновлює наявний запис та повертає оновлений ORM-об'єкт або None."""
        item = await self.get_by_id(record_id)
        if item is None:
            return None

        item.road_state = data.road_state
        item.x = data.agent_data.accelerometer.x
        item.y = data.agent_data.accelerometer.y
        item.z = data.agent_data.accelerometer.z
        item.latitude = data.agent_data.gps.latitude
        item.longitude = data.agent_data.gps.longitude
        item.timestamp = self._normalize_timestamp(data.agent_data.time)

        await self._session.flush()
        return item

    async def delete(self, record_id: int) -> ProcessedAgentDataORM | None:
        """Видаляє запис за id та повертає видалений ORM-об'єкт або None."""
        item = await self.get_by_id(record_id)
        if item is None:
            return None

        await self._session.delete(item)
        await self._session.flush()
        return item

    @staticmethod
    def _to_orm(data: ProcessedAgentData) -> ProcessedAgentDataORM:
        """Перетворює Pydantic-модель у ORM-об'єкт."""
        return ProcessedAgentDataORM(
            road_state=data.road_state,
            x=data.agent_data.accelerometer.x,
            y=data.agent_data.accelerometer.y,
            z=data.agent_data.accelerometer.z,
            latitude=data.agent_data.gps.latitude,
            longitude=data.agent_data.gps.longitude,
            timestamp=ProcessedAgentDataRepository._normalize_timestamp(data.agent_data.time),
        )

    @staticmethod
    def _normalize_timestamp(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value
        return value.astimezone(UTC).replace(tzinfo=None)
