from datetime import datetime, timezone

from src.edge.processor import process_agent_data
from src.models import Accelerometer, AggregatedData, Gps, RoadState


class TestProcessAgentData:
    def _make_data(self, *, y: float, z: float) -> AggregatedData:
        return AggregatedData(
            accelerometer=Accelerometer(x=0.1, y=y, z=z),
            gps=Gps(latitude=50.45, longitude=30.52),
            time=datetime(2026, 3, 20, 10, 0, tzinfo=timezone.utc),
        )

    def test_returns_good_for_small_vibrations(self):
        result = process_agent_data(self._make_data(y=50.0, z=16520.0))
        assert result.road_state is RoadState.GOOD

    def test_returns_warning_for_medium_y_spike(self):
        result = process_agent_data(self._make_data(y=150.0, z=16510.0))
        assert result.road_state is RoadState.WARNING

    def test_returns_bad_for_large_y_spike(self):
        result = process_agent_data(self._make_data(y=600.0, z=16510.0))
        assert result.road_state is RoadState.BAD

    def test_returns_bad_for_large_z_deviation(self):
        result = process_agent_data(self._make_data(y=20.0, z=14000.0))
        assert result.road_state is RoadState.BAD

    def test_preserves_original_agent_data(self):
        agent_data = self._make_data(y=90.0, z=16500.0)
        result = process_agent_data(agent_data)
        assert result.agent_data is agent_data
