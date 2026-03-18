from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Клас налаштувань застосунку."""

    mqtt_broker_host: str = "localhost"
    mqtt_broker_port: int = 1883
    mqtt_topic: str = "agent_data_topic"
    delay: float = 0.1
    batch_size: int = 5

    accelerometer_file: str = "data/accelerometer.csv"
    gps_file: str = "data/gps.csv"
    temperature_file: str | None = None

    log_level: str = "DEBUG"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
