import csv
from pathlib import Path

import pytest

from src.agent.file_datasource import FileDatasource
from src.models import AggregatedData


@pytest.fixture
def csv_files(tmp_path: Path) -> tuple[str, str]:
    """Створює тимчасові CSV-файли з тестовими даними."""
    acc_path = tmp_path / "accelerometer.csv"
    gps_path = tmp_path / "gps.csv"

    with acc_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["x", "y", "z"])
        writer.writeheader()
        for i in range(3):
            writer.writerow({"x": float(i), "y": float(i) * 0.5, "z": 9.8 + i})

    with gps_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["longitude", "latitude"])
        writer.writeheader()
        for i in range(3):
            writer.writerow({"longitude": 30.52 + i * 0.01, "latitude": 50.45 + i * 0.01})

    return str(acc_path), str(gps_path)


class TestStartStopReading:
    def test_start_opens_files(self, csv_files):
        ds = FileDatasource(*csv_files)
        ds.start_reading()
        assert ds._accelerometer_file is not None
        assert ds._gps_file is not None
        ds.stop_reading()

    def test_stop_clears_all_state(self, csv_files):
        ds = FileDatasource(*csv_files)
        ds.start_reading()
        ds.stop_reading()
        assert ds._accelerometer_file is None
        assert ds._gps_file is None
        assert ds._accelerometer_reader is None
        assert ds._gps_reader is None

    def test_double_stop_is_safe(self, csv_files):
        ds = FileDatasource(*csv_files)
        ds.start_reading()
        ds.stop_reading()
        ds.stop_reading()


class TestRead:
    def test_read_without_start_raises(self, csv_files):
        ds = FileDatasource(*csv_files)
        with pytest.raises(RuntimeError, match="start_reading"):
            ds.read()

    def test_read_returns_correct_batch_size(self, csv_files):
        ds = FileDatasource(*csv_files, batch_size=2)
        ds.start_reading()
        records = ds.read()
        ds.stop_reading()
        assert len(records) == 2

    def test_read_returns_aggregated_data(self, csv_files):
        ds = FileDatasource(*csv_files, batch_size=1)
        ds.start_reading()
        records = ds.read()
        ds.stop_reading()
        assert all(isinstance(r, AggregatedData) for r in records)

    def test_read_parses_values_correctly(self, csv_files):
        ds = FileDatasource(*csv_files, batch_size=1)
        ds.start_reading()
        record = ds.read()[0]
        ds.stop_reading()
        assert record.accelerometer.x == 0.0
        assert record.gps.longitude == pytest.approx(30.52)

    def test_circular_reading_wraps_around(self, csv_files):
        """Batch більший за кількість рядків — має читати з початку."""
        ds = FileDatasource(*csv_files, batch_size=5)
        ds.start_reading()
        records = ds.read()
        ds.stop_reading()
        assert len(records) == 5

    def test_two_sequential_reads(self, csv_files):
        ds = FileDatasource(*csv_files, batch_size=2)
        ds.start_reading()
        first = ds.read()
        second = ds.read()
        ds.stop_reading()
        assert len(first) == 2
        assert len(second) == 2
