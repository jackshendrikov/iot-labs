from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Enum, Float, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from models.processed_agent_data import RoadState
from src.db.base import Base
from src.models.sensor_type import SensorType

# Під PostgreSQL використовуємо JSONB (GIN-індекс + бінарний формат),
# під SQLite (тести) — загальний JSON, щоб ORM працював в обох середовищах
_JsonColumn = JSON().with_variant(JSONB(), "postgresql")


class ProcessedAgentDataORM(Base):
    __tablename__ = "processed_agent_data"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    road_state: Mapped[RoadState] = mapped_column(
        Enum(
            RoadState,
            native_enum=False,
            validate_strings=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
    )
    x: Mapped[float] = mapped_column(Float, nullable=False)
    y: Mapped[float] = mapped_column(Float, nullable=False)
    z: Mapped[float] = mapped_column(Float, nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class SensorReadingORM(Base):
    __tablename__ = "sensor_readings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    sensor_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    sensor_type: Mapped[SensorType] = mapped_column(
        Enum(
            SensorType,
            native_enum=False,
            validate_strings=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        index=True,
    )
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(_JsonColumn, nullable=False)
