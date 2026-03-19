import asyncio

from src.core.logger import logger
from src.hub.service import HubService


async def main() -> None:
    service = HubService()
    try:
        await service.start()
        await asyncio.Future()
    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info("Hub зупинено за запитом користувача")
    finally:
        await service.stop()


if __name__ == "__main__":
    asyncio.run(main())
