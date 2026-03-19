from datetime import datetime, timezone

import pytest

from src.models.accelerometer import Accelerometer
from src.models.aggregated_data import AggregatedData
from src.models.gps import Gps
from src.models.processed_agent_data import ProcessedAgentData, RoadState
from src.repository.processed_agent_data import ProcessedAgentDataRepository


def _make_data(road_state: RoadState = RoadState.GOOD) -> ProcessedAgentData:
    return ProcessedAgentData(
        road_state=road_state,
        agent_data=AggregatedData(
            accelerometer=Accelerometer(x=1.0, y=0.5, z=9.8),
            gps=Gps(latitude=50.45, longitude=30.52),
            time=datetime(2026, 3, 19, 10, 0, tzinfo=timezone.utc),
        ),
    )


class TestCreateBatch:
    async def test_returns_items_with_generated_ids(self, db_session):
        repo = ProcessedAgentDataRepository(db_session)
        items = await repo.create_batch([_make_data(), _make_data(RoadState.BAD)])
        await db_session.commit()
        assert len(items) == 2
        assert all(item.id is not None for item in items)

    async def test_persists_road_state(self, db_session):
        repo = ProcessedAgentDataRepository(db_session)
        [item] = await repo.create_batch([_make_data(RoadState.GOOD)])
        await db_session.commit()
        assert item.road_state == "good"

    async def test_empty_batch_returns_empty_list(self, db_session):
        repo = ProcessedAgentDataRepository(db_session)
        result = await repo.create_batch([])
        await db_session.commit()
        assert result == []

    async def test_converts_aware_timestamp_to_naive_utc(self, db_session):
        repo = ProcessedAgentDataRepository(db_session)
        source = _make_data(RoadState.GOOD)

        [item] = await repo.create_batch([source])
        await db_session.commit()

        assert item.timestamp.tzinfo is None
        assert item.timestamp == source.agent_data.time.replace(tzinfo=None)


class TestGetById:
    async def test_returns_correct_item(self, db_session):
        repo = ProcessedAgentDataRepository(db_session)
        [item] = await repo.create_batch([_make_data()])
        await db_session.commit()
        found = await repo.get_by_id(item.id)
        assert found is not None
        assert found.id == item.id

    async def test_returns_none_for_missing(self, db_session):
        repo = ProcessedAgentDataRepository(db_session)
        assert await repo.get_by_id(99999) is None

    async def test_fields_match_input(self, db_session):
        repo = ProcessedAgentDataRepository(db_session)
        [item] = await repo.create_batch([_make_data()])
        await db_session.commit()
        found = await repo.get_by_id(item.id)
        assert found.x == pytest.approx(1.0)
        assert found.latitude == pytest.approx(50.45)


class TestGetAll:
    async def test_returns_all_created_items(self, db_session):
        repo = ProcessedAgentDataRepository(db_session)
        await repo.create_batch([_make_data(), _make_data(RoadState.BAD), _make_data(RoadState.GOOD)])
        await db_session.commit()
        all_items = await repo.get_all()
        assert len(all_items) == 3

    async def test_empty_db_returns_empty_list(self, db_session):
        repo = ProcessedAgentDataRepository(db_session)
        assert await repo.get_all() == []


class TestUpdate:
    async def test_updates_road_state(self, db_session):
        repo = ProcessedAgentDataRepository(db_session)
        [item] = await repo.create_batch([_make_data(RoadState.GOOD)])
        await db_session.commit()
        updated = await repo.update(item.id, _make_data(RoadState.BAD))
        await db_session.commit()
        assert updated is not None
        assert updated.road_state == "bad"

    async def test_returns_none_for_missing(self, db_session):
        repo = ProcessedAgentDataRepository(db_session)
        result = await repo.update(99999, _make_data())
        assert result is None

    async def test_get_by_id_reflects_update(self, db_session):
        repo = ProcessedAgentDataRepository(db_session)
        [item] = await repo.create_batch([_make_data(RoadState.GOOD)])
        await db_session.commit()
        await repo.update(item.id, _make_data(RoadState.BAD))
        await db_session.commit()
        found = await repo.get_by_id(item.id)
        assert found.road_state == "bad"

    async def test_update_converts_aware_timestamp_to_naive_utc(self, db_session):
        repo = ProcessedAgentDataRepository(db_session)
        [item] = await repo.create_batch([_make_data(RoadState.GOOD)])
        await db_session.commit()

        updated_data = _make_data(RoadState.BAD)
        updated = await repo.update(item.id, updated_data)
        await db_session.commit()

        assert updated is not None
        assert updated.timestamp.tzinfo is None
        assert updated.timestamp == updated_data.agent_data.time.replace(tzinfo=None)


class TestDelete:
    async def test_removes_item_from_db(self, db_session):
        repo = ProcessedAgentDataRepository(db_session)
        [item] = await repo.create_batch([_make_data()])
        await db_session.commit()
        await repo.delete(item.id)
        await db_session.commit()
        assert await repo.get_by_id(item.id) is None

    async def test_returns_deleted_item(self, db_session):
        repo = ProcessedAgentDataRepository(db_session)
        [item] = await repo.create_batch([_make_data()])
        await db_session.commit()
        deleted = await repo.delete(item.id)
        assert deleted is not None
        assert deleted.id == item.id

    async def test_returns_none_for_missing(self, db_session):
        repo = ProcessedAgentDataRepository(db_session)
        assert await repo.delete(99999) is None
