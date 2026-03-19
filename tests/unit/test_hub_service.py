import asyncio

import pytest

from src.hub.service import HubService
from src.models import Accelerometer, AggregatedData, Gps, ProcessedAgentData, RoadState

_REDIS_KEY = "hub:processed_agent_data"


class FakeRedis:
    def __init__(self) -> None:
        self._storage: dict[str, list[str]] = {}

    async def lrange(self, key: str, start: int, end: int) -> list[str]:
        values = self._storage.get(key, [])
        if end == -1:
            return values[start:]
        return values[start : end + 1]

    async def ltrim(self, key: str, start: int, end: int) -> None:
        values = self._storage.get(key, [])
        if end == -1:
            self._storage[key] = values[start:]
            return
        self._storage[key] = values[start : end + 1]

    async def rpush(self, key: str, *values: str) -> None:
        self._storage.setdefault(key, []).extend(values)

    async def llen(self, key: str) -> int:
        return len(self._storage.get(key, []))

    async def aclose(self) -> None:
        return None


def _make_data(index: int) -> ProcessedAgentData:
    return ProcessedAgentData(
        road_state=RoadState.GOOD,
        agent_data=AggregatedData(
            accelerometer=Accelerometer(x=float(index), y=0.5, z=9.8),
            gps=Gps(latitude=50.45 + index, longitude=30.52 + index),
        ),
    )


@pytest.fixture
def redis_client() -> FakeRedis:
    return FakeRedis()


class TestHubService:
    async def test_flushes_batch_when_batch_size_reached(self, redis_client, monkeypatch):
        saved_batches: list[list[ProcessedAgentData]] = []

        async def save_batch(batch: list[ProcessedAgentData]) -> bool:
            saved_batches.append(list(batch))
            return True

        service = HubService(
            redis_client=redis_client,
            batch_size=2,
            flush_interval_seconds=60,
        )
        monkeypatch.setattr(service._gateway, "save_batch", save_batch)

        await service.start(enable_mqtt=False)
        await service.ingest(_make_data(1))
        await service.ingest(_make_data(2))
        await asyncio.wait_for(service._queue.join(), timeout=1)
        await service.stop()

        assert len(saved_batches) == 1
        assert len(saved_batches[0]) == 2
        assert await redis_client.llen(_REDIS_KEY) == 0

    async def test_flushes_partial_batch_on_stop(self, redis_client, monkeypatch):
        saved_batches: list[list[ProcessedAgentData]] = []

        async def save_batch(batch: list[ProcessedAgentData]) -> bool:
            saved_batches.append(list(batch))
            return True

        service = HubService(
            redis_client=redis_client,
            batch_size=10,
            flush_interval_seconds=60,
        )
        monkeypatch.setattr(service._gateway, "save_batch", save_batch)

        await service.start(enable_mqtt=False)
        await service.ingest(_make_data(1))
        await asyncio.wait_for(service._queue.join(), timeout=1)
        await service.stop()

        assert len(saved_batches) == 1
        assert len(saved_batches[0]) == 1
        assert await redis_client.llen(_REDIS_KEY) == 0

    async def test_moves_failed_batch_to_redis_and_retries_it(self, redis_client, monkeypatch):
        saved_batches: list[list[ProcessedAgentData]] = []
        responses = [False, True]

        async def save_batch(batch: list[ProcessedAgentData]) -> bool:
            saved_batches.append(list(batch))
            return responses.pop(0)

        service = HubService(
            redis_client=redis_client,
            batch_size=2,
            flush_interval_seconds=60,
        )
        monkeypatch.setattr(service._gateway, "save_batch", save_batch)

        await service.start(enable_mqtt=False)
        await service.ingest(_make_data(1))
        await service.ingest(_make_data(2))
        await asyncio.wait_for(service._queue.join(), timeout=1)

        assert await redis_client.llen(_REDIS_KEY) == 2

        await service.flush(force=True)
        await service.stop()

        assert len(saved_batches) == 2
        assert len(saved_batches[0]) == 2
        assert len(saved_batches[1]) == 2
        assert await redis_client.llen(_REDIS_KEY) == 0

    async def test_periodic_flush_saves_partial_batch(self, redis_client, monkeypatch):
        saved_batches: list[list[ProcessedAgentData]] = []

        async def save_batch(batch: list[ProcessedAgentData]) -> bool:
            saved_batches.append(list(batch))
            return True

        service = HubService(
            redis_client=redis_client,
            batch_size=10,
            flush_interval_seconds=0.01,
        )
        monkeypatch.setattr(service._gateway, "save_batch", save_batch)

        await service.start(enable_mqtt=False)
        await service.ingest(_make_data(1))
        await asyncio.wait_for(service._queue.join(), timeout=1)
        await asyncio.sleep(0.05)
        await service.stop()

        assert len(saved_batches) >= 1
        assert len(saved_batches[0]) == 1
        assert await redis_client.llen(_REDIS_KEY) == 0
