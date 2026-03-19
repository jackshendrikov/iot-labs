from fastapi import WebSocket

from src.core.logger import logger


class ConnectionManager:
    """Менеджер активних WebSocket-з'єднань."""

    def __init__(self) -> None:
        self._active: set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        """Приймає нове з'єднання та реєструє його."""
        await websocket.accept()
        self._active.add(websocket)
        logger.info(f"WebSocket підключено. Активних з'єднань: {len(self._active)}")

    def disconnect(self, websocket: WebSocket) -> None:
        """Видаляє з'єднання зі списку активних."""
        self._active.discard(websocket)
        logger.info(f"WebSocket відключено. Активних з'єднань: {len(self._active)}")

    async def broadcast(self, message: str) -> None:
        """Надсилає повідомлення всім підключеним клієнтам, ігноруючи проблемні з'єднання."""
        dead: set[WebSocket] = set()
        for ws in self._active:
            try:
                await ws.send_text(message)
            except Exception:
                dead.add(ws)
        self._active -= dead


manager = ConnectionManager()
