import uvicorn

from src.core.config import settings

if __name__ == "__main__":
    uvicorn.run(
        "src.api.app:app",
        host=settings.store_host,
        port=settings.store_port,
        reload=False,
    )
