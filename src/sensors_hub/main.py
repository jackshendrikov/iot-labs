import asyncio

from src.core.logger import logger
from src.sensors_hub.service import SensorsHubService


async def main() -> None:
    service = SensorsHubService()
    try:
        await service.start()
        await asyncio.Future()
    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info("Sensors Hub зупинено за запитом користувача")
    finally:
        await service.stop()


if __name__ == "__main__":
    asyncio.run(main())
