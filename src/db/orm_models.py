from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, Integer
from sqlalchemy.orm import Mapped, mapped_column

from models.processed_agent_data import RoadState
from src.db.base import Base


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
