from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    app_name: str = "VEXTRO API"
    app_version: str = "0.1.0"
    app_debug: bool = True

    db_host: str = "127.0.0.1"
    db_port: int = 5432
    db_name: str = "vextro_db"
    db_user: str = "vextro_app"
    db_password: str
    db_echo: bool = False

    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return one cached settings instance."""

    return Settings()


settings = get_settings()