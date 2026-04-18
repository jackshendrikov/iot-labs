"""CLI для генерації синтетичних показань нових сенсорів.

Приклади:
    python -m src.synthetic.main                       # лише CSV у data/
    python -m src.synthetic.main --seed-db             # + вставка у PostgreSQL
    python -m src.synthetic.main --output-dir data/ex  # інша тека вивчення
"""

import argparse
import asyncio
from pathlib import Path

from src.core.logger import logger
from src.db.base import async_session_factory, engine
from src.repository.sensor_reading import SensorReadingRepository
from src.synthetic.generator import generate_readings, write_csv_files


async def _seed_database(readings: list) -> None:
    """Вставляє згенеровані показання у БД через репозиторій."""
    async with async_session_factory() as session:
        repo = SensorReadingRepository(session)
        try:
            await repo.create_batch(readings)
            await session.commit()
        except Exception:
            await session.rollback()
            logger.exception("Не вдалося посіяти sensor_readings у БД")
            raise
    await engine.dispose()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Генератор синтетичних показань сенсорів.")
    parser.add_argument("--output-dir", type=Path, default=Path("data"))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--seed-db",
        action="store_true",
        help="Окрім CSV, записати показання у PostgreSQL (потрібен Store API up).",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    readings = generate_readings(seed=args.seed)
    written = write_csv_files(readings, args.output_dir)

    logger.info("Згенеровано %d показань:", len(readings))
    for sensor_type, path in written.items():
        logger.info("  %s -> %s", sensor_type.value, path)

    if args.seed_db:
        logger.info("Посіваємо sensor_readings у PostgreSQL...")
        asyncio.run(_seed_database(readings))
        logger.info("Готово: %d записів у sensor_readings", len(readings))


if __name__ == "__main__":
    main()
