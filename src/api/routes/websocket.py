"""WebSocket-маршрути для road та sensors каналів."""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from src.api.ws_manager import manager, sensors_manager

router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """WebSocket-ендпоінт для отримання нових записів дорожнього пайплайну в реальному часі."""
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@router.websocket("/ws/sensors")
async def sensors_websocket_endpoint(websocket: WebSocket) -> None:
    """WebSocket-ендпоінт для трансляції універсальних показань сенсорів."""
    await sensors_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        sensors_manager.disconnect(websocket)
