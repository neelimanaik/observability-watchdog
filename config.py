from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Observability Watchdog"
    db_url: str = "sqlite:///./watchdog.db"
    anomaly_window_minutes: int = 5
    anomaly_spike_multiplier: float = 3.0
    alert_webhook_url: str = ""
    scheduler_interval_seconds: int = 60
    groq_api_key: str = ""
    groq_model: str = "llama3-8b-8192"
    groq_max_tokens: int = 512

    class Config:
        env_file = ".env"


settings = Settings()
