"""Фабрика та життєвий цикл Store API."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from starlette.staticfiles import StaticFiles

from src.api.metrics import PrometheusMiddleware
from src.api.network_analytics import NetworkAnomalyDetector
from src.api.router import router
from src.core.logger import logger
from src.db.base import engine


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncGenerator[None, None]:
    """Управляє ресурсами застосунку: ініціалізація та завершення."""
    logger.info("Store API запускається...")

    detector = NetworkAnomalyDetector()
    await detector.start()
    application.state.network_anomaly_detector = detector

    try:
        yield
    finally:
        await detector.stop()
        await engine.dispose()
        logger.info("Store API зупинено. З'єднання з БД закрито.")


def create_app() -> FastAPI:
    """Фабрика FastAPI-застосунку."""
    application = FastAPI(
        title="UrbanPulse IoT: Store API",
        description="API для зберігання та отримання телеметрії міських, транспортних та інфраструктурних сенсорів.",
        version="1.4.0",
        lifespan=lifespan,
    )

    application.add_middleware(PrometheusMiddleware)
    application.include_router(router)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:8000"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.mount("/ui", StaticFiles(directory="src/ui", html=True), name="UI")

    return application


app = create_app()
