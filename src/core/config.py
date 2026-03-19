from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Клас налаштувань застосунку (агент + store)."""

    # --- Агент / MQTT ---
    mqtt_broker_host: str = "localhost"
    mqtt_broker_port: int = 1883
    mqtt_topic: str = "agent_data_topic"
    delay: float = 0.1
    batch_size: int = 5

    accelerometer_file: str = "data/accelerometer.csv"
    gps_file: str = "data/gps.csv"
    temperature_file: str | None = None

    # --- Store / PostgreSQL ---
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "user"
    postgres_password: str = "pass"
    postgres_db: str = "road_vision"
    db_echo: bool = False

    store_host: str = "0.0.0.0"
    store_port: int = 8000

    # --- Загальне ---
    log_level: str = "DEBUG"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def database_url(self) -> str:
        """Повертає URL підключення до PostgreSQL для asyncpg."""
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


settings = Settings()
