from src.core.logger import logger
from src.edge.adapters import AgentMqttAdapter, HubMqttAdapter


def main() -> None:
    """Запускає edge-сервіс."""
    adapter = AgentMqttAdapter(hub_gateway=HubMqttAdapter())
    try:
        adapter.connect()
        logger.info("Edge запущено")
        adapter.start()
    except KeyboardInterrupt:
        logger.info("Edge зупинено за запитом користувача")
    finally:
        adapter.stop()


if __name__ == "__main__":
    main()
