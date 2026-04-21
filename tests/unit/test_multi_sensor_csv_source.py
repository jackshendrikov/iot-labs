"""Тести для merge-sort читача сенсорних CSV."""

from pathlib import Path

from src.models.sensor_type import SensorType
from src.sensors_agent.csv_source import MultiSensorCsvSource

_CSV_HEADER = "sensor_id,sensor_type,latitude,longitude,timestamp,payload\n"


def _write_csv(path: Path, rows: list[str]) -> None:
    """Швидко готує CSV-файл для тестового сценарію."""
    path.write_text(_CSV_HEADER + "\n".join(rows) + "\n", encoding="utf-8")


class TestMultiSensorCsvSource:
    def test_single_file_yields_all_readings(self, tmp_path: Path) -> None:
        path = tmp_path / "car_parks.csv"
        _write_csv(
            path,
            [
                "car_park-000,car_park,50.45,30.52,2026-04-17T10:00:00+00:00,"
                '"{""kind"": ""car_park"", ""total_spots"": 100, ""occupied_spots"": 20}"',
                "car_park-000,car_park,50.45,30.52,2026-04-17T11:00:00+00:00,"
                '"{""kind"": ""car_park"", ""total_spots"": 100, ""occupied_spots"": 55}"',
            ],
        )
        source = MultiSensorCsvSource({SensorType.CAR_PARK: str(path)})
        readings = list(source.iter_readings())
        assert len(readings) == 2
        assert readings[0].payload.occupied_spots == 20
        assert readings[1].payload.occupied_spots == 55

    def test_merge_sort_interleaves_by_timestamp(self, tmp_path: Path) -> None:
        """Показання з різних CSV видаються у хронологічному порядку."""
        parks = tmp_path / "parks.csv"
        lights = tmp_path / "lights.csv"
        _write_csv(
            parks,
            [
                "p-1,car_park,50.45,30.52,2026-04-17T10:00:00+00:00,"
                '"{""kind"": ""car_park"", ""total_spots"": 10, ""occupied_spots"": 1}"',
                "p-1,car_park,50.45,30.52,2026-04-17T12:00:00+00:00,"
                '"{""kind"": ""car_park"", ""total_spots"": 10, ""occupied_spots"": 2}"',
            ],
        )
        _write_csv(
            lights,
            [
                "l-1,traffic_light,50.44,30.51,2026-04-17T11:00:00+00:00,"
                '"{""kind"": ""traffic_light"", ""state"": ""red"", ""cycle_seconds"": 60, ""queue_length"": 3}"',
            ],
        )
        source = MultiSensorCsvSource(
            {
                SensorType.CAR_PARK: str(parks),
                SensorType.TRAFFIC_LIGHT: str(lights),
            }
        )
        readings = list(source.iter_readings())
        assert [r.metadata.sensor_type for r in readings] == [
            SensorType.CAR_PARK,
            SensorType.TRAFFIC_LIGHT,
            SensorType.CAR_PARK,
        ]
        timestamps = [r.metadata.timestamp for r in readings]
        assert timestamps == sorted(timestamps)

    def test_missing_file_is_skipped(self, tmp_path: Path) -> None:
        existing = tmp_path / "parks.csv"
        _write_csv(
            existing,
            [
                "p-1,car_park,50.45,30.52,2026-04-17T10:00:00+00:00,"
                '"{""kind"": ""car_park"", ""total_spots"": 5, ""occupied_spots"": 1}"',
            ],
        )
        source = MultiSensorCsvSource(
            {
                SensorType.CAR_PARK: str(existing),
                SensorType.AIR_QUALITY: str(tmp_path / "missing.csv"),
            }
        )
        readings = list(source.iter_readings())
        assert len(readings) == 1

    def test_none_path_is_ignored(self, tmp_path: Path) -> None:
        source = MultiSensorCsvSource({SensorType.CAR_PARK: None})
        assert list(source.iter_readings()) == []

    def test_stops_when_exhausted_no_loop(self, tmp_path: Path) -> None:
        path = tmp_path / "parks.csv"
        _write_csv(
            path,
            [
                "p-1,car_park,50.45,30.52,2026-04-17T10:00:00+00:00,"
                '"{""kind"": ""car_park"", ""total_spots"": 5, ""occupied_spots"": 1}"',
            ],
        )
        source = MultiSensorCsvSource({SensorType.CAR_PARK: str(path)})
        readings = list(source.iter_readings())
        assert len(readings) == 1
        assert len(list(source.iter_readings())) == 1
