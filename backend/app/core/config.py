from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """VEXTRO application configuration."""

    app_name: str = "VEXTRO API"
    app_version: str = "0.1.0"
    app_debug: bool = True

    db_host: str = "127.0.0.1"
    db_port: int = 5432
    db_name: str = "vextro_db"
    db_user: str = "vextro_app"
    db_password: str
    db_echo: bool = False

    test_db_name: str = "vextro_test_db"

    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    ingestion_api_key: str | None = None
    cors_origins: str = (
        "http://localhost:5173,http://127.0.0.1:5173"
    )

    @property
    def cors_origin_list(self) -> list[str]:
        """Return normalized configured frontend origins."""

        return [
            origin.strip()
            for origin in self.cors_origins.split(",")
            if origin.strip()
        ]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return the cached application settings."""

    return Settings()


settings = get_settings()
