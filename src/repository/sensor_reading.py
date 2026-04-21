"""Репозиторій для універсальних сенсорних показань."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.orm_models import SensorReadingORM
from src.models.sensor_reading import SensorReading
from src.models.sensor_type import SensorType


class SensorReadingRepository:
    """Репозиторій для CRUD-операцій над універсальними показаннями сенсорів."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_batch(self, items: list[SensorReading]) -> list[SensorReadingORM]:
        """Зберігає список показань у БД та повертає ORM-об'єкти."""
        orm_items = [self._to_orm(item) for item in items]
        self._session.add_all(orm_items)
        await self._session.flush()
        return orm_items

    async def get_by_id(self, record_id: int) -> SensorReadingORM | None:
        """Повертає запис за його id або None, якщо не знайдено."""
        result = await self._session.execute(select(SensorReadingORM).where(SensorReadingORM.id == record_id))
        return result.scalar_one_or_none()

    async def list_filtered(
        self,
        sensor_type: SensorType | None = None,
        sensor_id: str | None = None,
        limit: int = 1000,
    ) -> list[SensorReadingORM]:
        """Повертає показання з опційною фільтрацією за типом та/або id сенсора."""
        stmt = select(SensorReadingORM)
        if sensor_type is not None:
            stmt = stmt.where(SensorReadingORM.sensor_type == sensor_type)
        if sensor_id is not None:
            stmt = stmt.where(SensorReadingORM.sensor_id == sensor_id)
        stmt = stmt.order_by(SensorReadingORM.timestamp.desc()).limit(limit)

        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def delete(self, record_id: int) -> SensorReadingORM | None:
        """Видаляє запис за id та повертає видалений ORM-об'єкт або None."""
        item = await self.get_by_id(record_id)
        if item is None:
            return None

        await self._session.delete(item)
        await self._session.flush()
        return item

    def _to_orm(self, data: SensorReading) -> SensorReadingORM:
        """Перетворює універсальну Pydantic-модель у ORM-об'єкт."""
        payload = data.payload.model_dump(mode="json")
        return SensorReadingORM(
            sensor_id=data.metadata.sensor_id,
            sensor_type=data.metadata.sensor_type,
            latitude=data.metadata.location.latitude,
            longitude=data.metadata.location.longitude,
            timestamp=self._normalize_timestamp(data.metadata.timestamp),
            payload=payload,
            anomaly_flags=list(data.metadata.anomaly_flags),
        )

    @staticmethod
    def _normalize_timestamp(value: datetime) -> datetime:
        """Нормалізує timestamp до naive UTC для зберігання в БД."""
        if value.tzinfo is None:
            return value
        return value.astimezone(UTC).replace(tzinfo=None)
