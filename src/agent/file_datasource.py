import csv
from collections.abc import Iterator
from typing import TextIO

from src.core.logger import logger
from src.models import Accelerometer, AggregatedData, Gps, TemperatureSensor

_CsvRow = dict[str, str]
_CsvReader = Iterator[_CsvRow]


class FileDatasource:
    """Клас джерела даних для читання з CSV-файлів."""

    def __init__(
        self,
        accelerometer_filename: str,
        gps_filename: str,
        temperature_filename: str | None = None,
        batch_size: int = 5,
    ) -> None:
        """Ініціалізує джерело даних."""
        self.accelerometer_filename = accelerometer_filename
        self.gps_filename = gps_filename
        self.temperature_filename = temperature_filename
        self.batch_size = batch_size

        self._accelerometer_file: TextIO | None = None
        self._gps_file: TextIO | None = None
        self._temperature_file: TextIO | None = None

        self._accelerometer_reader: _CsvReader | None = None
        self._gps_reader: _CsvReader | None = None
        self._temperature_reader: _CsvReader | None = None

    def start_reading(self) -> None:
        """Підготовка файлів та ініціалізація читачів."""
        logger.debug("Початок читання файлів")
        self.stop_reading()

        # Відкриваємо файли у текстовому режимі
        self._accelerometer_file = open(self.accelerometer_filename, encoding="utf-8", newline="")
        self._gps_file = open(self.gps_filename, encoding="utf-8", newline="")

        # Створюємо DictReader для кожного файлу
        self._accelerometer_reader = csv.DictReader(self._accelerometer_file)
        self._gps_reader = csv.DictReader(self._gps_file)

        if self.temperature_filename:
            self._temperature_file = open(self.temperature_filename, encoding="utf-8", newline="")
            self._temperature_reader = csv.DictReader(self._temperature_file)

    def read(self) -> list[AggregatedData]:
        """Читає batch_size записів з файлів та повертає список агрегованих даних."""
        if not self._accelerometer_reader or not self._gps_reader:
            raise RuntimeError("Читання не ініціалізоване. Викличте start_reading() перед read().")

        records: list[AggregatedData] = []
        for _ in range(self.batch_size):
            # Зчитуємо наступний рядок акселерометра і GPS
            acc_row = self._next_row(self._accelerometer_reader, self._accelerometer_file, self.accelerometer_filename)  # type: ignore
            gps_row = self._next_row(self._gps_reader, self._gps_file, self.gps_filename)  # type: ignore

            # Побудова об'єктів
            accelerometer = Accelerometer(
                x=float(acc_row.get("x", "0")),
                y=float(acc_row.get("y", "0")),
                z=float(acc_row.get("z", "0")),
            )
            gps = Gps(
                longitude=float(gps_row.get("longitude", "0")),
                latitude=float(gps_row.get("latitude", "0")),
            )
            aggregated = AggregatedData(accelerometer=accelerometer, gps=gps)

            # Читання температурного датчика, якщо файл задано
            if self.temperature_filename and self._temperature_reader:
                temp_row = self._next_row(self._temperature_reader, self._temperature_file, self.temperature_filename)  # type: ignore
                temperature_sensor = TemperatureSensor(
                    temperature=float(temp_row.get("temperature", "0")),
                    humidity=float(temp_row.get("humidity", "0")),
                    gps=Gps(
                        longitude=float(temp_row.get("longitude", "0")),
                        latitude=float(temp_row.get("latitude", "0")),
                    ),
                )
                aggregated.temperature_sensor = temperature_sensor

            records.append(aggregated)
        return records

    def stop_reading(self) -> None:
        """Закриває відкриті файли та скидає читачі."""
        for attr in ("_accelerometer_file", "_gps_file", "_temperature_file"):
            if file := getattr(self, attr):
                file.close()
            setattr(self, attr, None)

        self._accelerometer_reader = None
        self._gps_reader = None
        self._temperature_reader = None
        logger.debug("Читання файлів завершено та ресурси звільнено")

    def _next_row(self, reader: _CsvReader, file_obj: TextIO, filename: str) -> _CsvRow:
        """Отримує наступний рядок з reader, перезапускаючи читання у разі необхідності."""
        try:
            return next(reader)
        except StopIteration:
            # Коли дочитали до кінця, починаємо спочатку
            new_reader = self._reset_reader(file_obj, filename)

            # Оновлюємо відповідний reader залежно від імені файлу
            match filename:
                case self.accelerometer_filename:
                    self._accelerometer_reader = new_reader
                case self.gps_filename:
                    self._gps_reader = new_reader
                case self.temperature_filename:
                    self._temperature_reader = new_reader
                case _:
                    pass

            # Повертаємо перший рядок після перезапуску
            try:
                return next(new_reader)
            except StopIteration as exc:
                raise RuntimeError(f"Файл {filename} не містить даних.") from exc

    @staticmethod
    def _reset_reader(file_obj: TextIO, filename: str) -> csv.DictReader:
        """Повертає новий DictReader з початку файлу."""
        logger.debug(f"Досягнуто кінця файлу {filename}. Перезапуск читання з початку.")
        file_obj.seek(0)
        return csv.DictReader(file_obj)
