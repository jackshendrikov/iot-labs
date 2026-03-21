from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from starlette.staticfiles import StaticFiles

from src.api.router import router
from src.core.logger import logger
from src.db.base import engine


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncGenerator[None, None]:
    """Управляє ресурсами застосунку: ініціалізація та завершення."""
    logger.info("Store API запускається...")
    yield
    await engine.dispose()
    logger.info("Store API зупинено. З'єднання з БД закрито.")


def create_app() -> FastAPI:
    """Фабрика FastAPI-застосунку."""
    application = FastAPI(
        title="Road Vision: Store API",
        description="API для зберігання та отримання оброблених даних про стан дорожнього покриття.",
        version="1.3.0",
        lifespan=lifespan,
    )

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
