from typing import Literal

from pydantic import BaseModel, Field, computed_field, model_validator


class CarParkPayload(BaseModel):
    """Дані сенсора паркомісця: загальна та зайнята ємність."""

    kind: Literal["car_park"] = "car_park"

    total_spots: int = Field(gt=0, description="Загальна кількість місць у паркінгу.")
    occupied_spots: int = Field(ge=0, description="Кількість зайнятих місць.")
    avg_stay_minutes: float | None = Field(
        default=None,
        ge=0.0,
        description="Середня тривалість паркування за останню годину (хв).",
    )

    @model_validator(mode="after")
    def _check_occupancy(self) -> "CarParkPayload":
        if self.occupied_spots > self.total_spots:
            raise ValueError("occupied_spots не може перевищувати total_spots")
        return self

    @computed_field  # type: ignore[prop-decorator]
    @property
    def occupancy_rate(self) -> float:
        """Відсоток зайнятості паркінгу (0.0 — 1.0)."""
        return self.occupied_spots / self.total_spots
