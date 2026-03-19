from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from src.api.ws_manager import manager

router = APIRouter()


@router.websocket("/ws/")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """WebSocket-ендпоінт для отримання нових записів у реальному часі."""
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
