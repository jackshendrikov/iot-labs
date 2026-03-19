from unittest.mock import AsyncMock, MagicMock

import pytest

from src.api.ws_manager import ConnectionManager


@pytest.fixture
def manager() -> ConnectionManager:
    return ConnectionManager()


def _make_ws(send_side_effect=None) -> MagicMock:
    ws = MagicMock()
    ws.accept = AsyncMock()
    ws.send_text = AsyncMock(side_effect=send_side_effect)
    return ws


class TestConnect:
    async def test_accept_is_called(self, manager):
        ws = _make_ws()
        await manager.connect(ws)
        ws.accept.assert_awaited_once()

    async def test_ws_added_to_active(self, manager):
        ws = _make_ws()
        await manager.connect(ws)
        assert ws in manager._active

    async def test_multiple_connections(self, manager):
        ws1, ws2 = _make_ws(), _make_ws()
        await manager.connect(ws1)
        await manager.connect(ws2)
        assert len(manager._active) == 2


class TestDisconnect:
    def test_removes_from_active(self, manager):
        ws = _make_ws()
        manager._active.add(ws)
        manager.disconnect(ws)
        assert ws not in manager._active

    def test_nonexistent_does_not_raise(self, manager):
        manager.disconnect(_make_ws())

    def test_other_connections_unaffected(self, manager):
        ws1, ws2 = _make_ws(), _make_ws()
        manager._active = {ws1, ws2}
        manager.disconnect(ws1)
        assert ws2 in manager._active


class TestBroadcast:
    async def test_sends_to_all_active(self, manager):
        ws1, ws2 = _make_ws(), _make_ws()
        manager._active = {ws1, ws2}
        await manager.broadcast("hello")
        ws1.send_text.assert_awaited_once_with("hello")
        ws2.send_text.assert_awaited_once_with("hello")

    async def test_dead_connection_removed(self, manager):
        good = _make_ws()
        dead = _make_ws(send_side_effect=Exception("closed"))
        manager._active = {good, dead}
        await manager.broadcast("ping")
        assert good in manager._active
        assert dead not in manager._active

    async def test_good_connection_still_receives_after_dead_removed(self, manager):
        good = _make_ws()
        dead = _make_ws(send_side_effect=Exception("closed"))
        manager._active = {good, dead}
        await manager.broadcast("ping")
        good.send_text.assert_awaited_once_with("ping")

    async def test_empty_set_does_not_raise(self, manager):
        await manager.broadcast("silence")
