from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from src.db.orm_models import ProcessedAgentDataORM
from src.models.accelerometer import Accelerometer
from src.models.aggregated_data import AggregatedData
from src.models.gps import Gps
from src.models.processed_agent_data import ProcessedAgentData, ProcessedAgentDataInDB, RoadState


class TestRoadState:
    def test_enum_values_are_strings(self):
        assert RoadState.GOOD == "good"
        assert RoadState.BAD == "bad"
        assert RoadState.WARNING == "warning"

    def test_road_state_is_str_subclass(self):
        assert isinstance(RoadState.GOOD, str)

    def test_all_values_covered(self):
        values = {v.value for v in RoadState}
        assert values == {"good", "bad", "warning"}


class TestProcessedAgentData:
    def _make(self, road_state: str = "good") -> ProcessedAgentData:
        return ProcessedAgentData(
            road_state=road_state,
            agent_data=AggregatedData(
                accelerometer=Accelerometer(x=1.0, y=0.5, z=9.8),
                gps=Gps(latitude=50.45, longitude=30.52),
                time=datetime(2026, 3, 19, 10, 0, tzinfo=timezone.utc),
            ),
        )

    def test_valid_creation(self):
        data = self._make("good")
        assert data.road_state == RoadState.GOOD
        assert data.agent_data.gps.latitude == 50.45
        assert data.agent_data.accelerometer.z == 9.8

    def test_invalid_road_state_raises(self):
        with pytest.raises(ValidationError):
            self._make("unknown_state")

    def test_road_state_coerced_from_string(self):
        data = self._make("bad")
        assert data.road_state is RoadState.BAD

    def test_time_defaults_to_utc_if_omitted(self):
        data = ProcessedAgentData(
            road_state="good",
            agent_data={
                "accelerometer": {"x": 0.0, "y": 0.0, "z": 0.0},
                "gps": {"latitude": 0.0, "longitude": 0.0},
            },
        )
        assert data.agent_data.time is not None
        assert data.agent_data.time.tzinfo is not None


class TestProcessedAgentDataInDB:
    def _make_orm(self, road_state: str = "good") -> ProcessedAgentDataORM:
        return ProcessedAgentDataORM(
            id=1,
            road_state=road_state,
            x=1.0,
            y=0.5,
            z=9.8,
            latitude=50.45,
            longitude=30.52,
            timestamp=datetime(2026, 3, 19, 10, 0, tzinfo=timezone.utc),
        )

    def test_from_orm_attributes(self):
        result = ProcessedAgentDataInDB.model_validate(self._make_orm())
        assert result.id == 1
        assert result.road_state == RoadState.GOOD
        assert result.x == 1.0
        assert result.latitude == 50.45

    def test_invalid_road_state_in_db_raises(self):
        with pytest.raises(ValidationError):
            ProcessedAgentDataInDB.model_validate(self._make_orm("broken"))
