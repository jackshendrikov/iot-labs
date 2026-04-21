"""Агрегатор усіх FastAPI-роутерів проєкту."""

from fastapi import APIRouter

from src.api.metrics import metrics_router
from src.api.routes.health import router as health_router
from src.api.routes.network_anomalies import router as network_anomalies_router
from src.api.routes.processed_agent_data import router as processed_agent_data_router
from src.api.routes.sensor_readings import router as sensor_readings_router
from src.api.routes.websocket import router as websocket_router

router = APIRouter()
router.include_router(health_router)
router.include_router(metrics_router)
router.include_router(processed_agent_data_router)
router.include_router(sensor_readings_router)
router.include_router(network_anomalies_router)
router.include_router(websocket_router)
