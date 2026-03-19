from fastapi import APIRouter

from src.api.routes.health import router as health_router
from src.api.routes.processed_agent_data import router as processed_agent_data_router
from src.api.routes.websocket import router as websocket_router

router = APIRouter()
router.include_router(health_router)
router.include_router(processed_agent_data_router)
router.include_router(websocket_router)
