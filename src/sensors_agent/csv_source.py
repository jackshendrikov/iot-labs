import csv
import io
import json
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from src.core.logger import logger
from src.models.sensor_reading import SensorReading
from src.models.sensor_type import SensorType


@dataclass(frozen=True)
class _Row:
    timestamp: datetime
    reading: SensorReading


class MultiSensorCsvSource:
    """Читає CSV-файли всіх типів сенсорів та повертає показання у хронологічному порядку.

    Файли зберігаються у компактному flat-форматі (див. `synthetic.generator`):
    колонки `sensor_id`, `sensor_type`, `latitude`, `longitude`, `timestamp`, `payload`,
    де `payload` — JSON-рядок із типоспецифічними полями (discriminator — `kind`).
    """

    def __init__(self, files: dict[SensorType, str | None]) -> None:
        self._files: dict[SensorType, Path] = {sensor_type: Path(path) for sensor_type, path in files.items() if path}

    def iter_readings(self) -> Iterator[SensorReading]:
        """Генерує `SensorReading` відсортовані по `timestamp` з усіх наявних файлів."""
        opened: list[io.TextIOWrapper] = []
        readers: list[tuple[SensorType, Iterator[dict[str, str]]]] = []

        try:
            for sensor_type, path in self._files.items():
                if not path.exists():
                    logger.warning(f"CSV-файл {path} не знайдено, пропускаємо {sensor_type.value}")
                    continue
                fh = path.open("r", encoding="utf-8", newline="")
                opened.append(fh)
                readers.append((sensor_type, csv.DictReader(fh)))

            heads: list[_Row | None] = [self._next_row(reader, st) for st, reader in readers]

            while any(head is not None for head in heads):
                min_idx = min(
                    (i for i, head in enumerate(heads) if head is not None),
                    key=lambda i: heads[i].timestamp,  # type: ignore[union-attr]
                )
                head = heads[min_idx]
                assert head is not None
                yield head.reading

                sensor_type, reader = readers[min_idx]
                heads[min_idx] = self._next_row(reader, sensor_type)

            logger.info("Всі CSV-джерела вичерпано — агент припиняє публікацію.")
        finally:
            for fh in opened:
                fh.close()

    def iter_time_slices(self) -> Iterator[list[SensorReading]]:
        """Групує показання в зрізи часу, щоб один крок містив усі сенсори з тим самим timestamp."""
        current_timestamp: datetime | None = None
        batch: list[SensorReading] = []

        for reading in self.iter_readings():
            timestamp = reading.metadata.timestamp
            if current_timestamp is None or timestamp == current_timestamp:
                batch.append(reading)
                current_timestamp = timestamp
                continue

            yield batch
            batch = [reading]
            current_timestamp = timestamp

        if batch:
            yield batch

    @staticmethod
    def _next_row(reader: Iterator[dict[str, str]], sensor_type: SensorType) -> _Row | None:
        """Читає наступний рядок CSV та перетворює на `SensorReading`."""
        try:
            raw = next(reader)
        except StopIteration:
            return None

        timestamp = datetime.fromisoformat(raw["timestamp"])
        payload = json.loads(raw["payload"])

        reading = SensorReading.model_validate(
            {
                "metadata": {
                    "sensor_id": raw["sensor_id"],
                    "sensor_type": sensor_type.value,
                    "location": {
                        "latitude": float(raw["latitude"]),
                        "longitude": float(raw["longitude"]),
                    },
                    "timestamp": timestamp.isoformat(),
                },
                "payload": payload,
            }
        )
        return _Row(timestamp=timestamp, reading=reading)
