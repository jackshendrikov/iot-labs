from collections.abc import Sequence

import httpx

from src.core.config import settings
from src.core.logger import logger
from src.models.processed_agent_data import ProcessedAgentData


class StoreApiGateway:
    """Адаптер для збереження batch оброблених даних через Store API."""

    def __init__(self) -> None:
        self._endpoint = f"{settings.store_api_base_url}/processed_agent_data/"
        self._client = httpx.AsyncClient(timeout=10.0)

    async def close(self) -> None:
        await self._client.aclose()

    async def save_batch(self, batch: Sequence[ProcessedAgentData]) -> bool:
        """Асинхронно надсилає batch оброблених даних до Store API."""
        if not batch:
            return True

        payload = [item.model_dump(mode="json") for item in batch]
        try:
            response = await self._client.post(self._endpoint, json=payload)
        except httpx.HTTPError:
            logger.exception("Помилка HTTP при відправці батча на Store API")
            return False

        if response.status_code == 201:
            logger.debug(f"Батч з {len(batch)} записів успішно збережено на Store API")
            return True

        logger.warning(f"Store API повернув код {response.status_code} при збереженні батча: {response.text}")
        return False
