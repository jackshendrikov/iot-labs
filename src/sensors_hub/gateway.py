"""HTTP-адаптер Sensors Hub для пакетного збереження сенсорних показань."""

from collections.abc import Sequence

import httpx

from src.core.config import settings
from src.core.logger import logger
from src.models.sensor_reading import SensorReading


class SensorStoreApiGateway:
    """Адаптер для batch-збереження `SensorReading` у Store API."""

    def __init__(self) -> None:
        self._endpoint = f"{settings.store_api_base_url}/sensor_readings/"
        self._client = httpx.AsyncClient(timeout=10.0)

    async def close(self) -> None:
        """Закриває внутрішній HTTP-клієнт."""
        await self._client.aclose()

    async def save_batch(self, batch: Sequence[SensorReading]) -> bool:
        """Асинхронно надсилає batch показань сенсорів у Store API."""
        if not batch:
            return True

        payload = [item.model_dump(mode="json") for item in batch]
        try:
            response = await self._client.post(self._endpoint, json=payload)
        except httpx.HTTPError:
            logger.exception("Sensors Hub: помилка HTTP при відправці батча в Store API")
            return False

        if response.status_code == 201:
            logger.debug(f"Sensors Hub: батч з {len(batch)} показань успішно збережено")
            return True

        logger.warning(f"Sensors Hub: Store API повернув код {response.status_code}: {response.text}")
        return False
