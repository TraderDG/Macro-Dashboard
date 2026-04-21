from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    APP_ENV: str = "development"
    APP_SECRET_KEY: str = "change_in_production"
    CORS_ORIGINS: str = "http://localhost:3000"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://macro:macro_secret@timescaledb:5432/macrodb"
    DATABASE_URL_SYNC: str = "postgresql://macro:macro_secret@timescaledb:5432/macrodb"

    # Redis / Celery
    REDIS_URL: str = "redis://redis:6379/0"

    # API Keys
    FRED_API_KEY: str = ""
    ALPHA_VANTAGE_KEY: str = ""
    GNEWS_API_KEY: str = ""

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",")]

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
