"""Конфігурація всіх сервісів UrbanPulse IoT через pydantic-settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Єдина модель налаштувань для road, sensors та observability-контурів."""

    # --- Агент / MQTT ---
    mqtt_broker_host: str = "localhost"
    mqtt_broker_port: int = 1883
    mqtt_topic: str = "agent_data_topic"
    delay: float = 5
    batch_size: int = 5
    loop_reading: bool = False

    accelerometer_file: str = "data/accelerometer.csv"
    gps_file: str = "data/gps.csv"
    temperature_file: str | None = None

    # --- Store / PostgreSQL ---
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "user"
    postgres_password: str = "pass"
    postgres_db: str = "urbanpulse"
    db_echo: bool = False

    store_host: str = "0.0.0.0"
    store_port: int = 8000

    # --- Hub / Redis ---
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0

    hub_batch_size: int = 10
    hub_flush_interval_seconds: float = 60.0
    hub_mqtt_topic: str = "processed_agent_data_topic"

    # Store API URL (звідки Hub відправляє дані)
    store_api_host: str = "localhost"
    store_api_port: int = 8000

    # --- Universal Sensors ---
    # Агент публікує сирі показання; Edge додає anomaly_flags і передає їх далі до Hub
    sensors_mqtt_topic: str = "sensor_data_topic"
    sensors_hub_mqtt_topic: str = "processed_sensor_data_topic"
    sensors_delay: float = 2.0
    sensors_batch_size: int = 8
    sensors_loop_reading: bool = True
    sensors_hub_batch_size: int = 16
    sensors_hub_flush_interval_seconds: float = 10.0

    # Шляхи до CSV, які читає Sensors Agent
    car_parks_file: str = "data/car_parks.csv"
    traffic_lights_file: str = "data/traffic_lights.csv"
    air_quality_file: str = "data/air_quality.csv"
    energy_meters_file: str = "data/energy_meters.csv"

    # --- Network analytics ---
    network_anomaly_window_seconds: float = 15.0
    network_anomaly_zscore_threshold: float = 2.2
    network_anomaly_min_samples: int = 4

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

    @property
    def redis_url(self) -> str:
        """Повертає URL підключення до Redis."""
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    @property
    def store_api_base_url(self) -> str:
        """Повертає базовий URL Store API для Hub-адаптера."""
        return f"http://{self.store_api_host}:{self.store_api_port}"


settings = Settings()
