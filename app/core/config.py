"""Конфигурация приложения через переменные окружения."""
from functools import lru_cache
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # DB
    database_url: str = Field(alias="DATABASE_URL")

    # JWT
    jwt_secret: str = Field(alias="JWT_SECRET")
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    jwt_expire_minutes: int = Field(default=30, alias="JWT_EXPIRE_MINUTES")

    # App
    app_timezone: str = Field(default="Europe/Moscow", alias="APP_TIMEZONE")
    pickup_address: str = Field(default="г. Москва, ул. Кондитерская, д. 1", alias="PICKUP_ADDRESS")
    pickup_hours: str = Field(default="Ежедневно 09:00–20:00", alias="PICKUP_HOURS")
    allowed_origins: str = Field(default="http://localhost:5173", alias="ALLOWED_ORIGINS")
    login_rate_limit: int = Field(default=10, alias="LOGIN_RATE_LIMIT")

    @property
    def origins_list(self) -> List[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
