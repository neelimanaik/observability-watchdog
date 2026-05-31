from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Observability Watchdog"
    db_url: str = "sqlite:///./watchdog.db"
    anomaly_window_minutes: int = 5
    anomaly_spike_multiplier: float = 3.0
    alert_webhook_url: str = ""
    scheduler_interval_seconds: int = 60

    class Config:
        env_file = ".env"


settings = Settings()
