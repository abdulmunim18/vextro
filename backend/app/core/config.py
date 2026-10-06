from functools import lru_cache
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

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
    email_otp_expire_minutes: int = 10
    email_otp_resend_cooldown_seconds: int = 60
    email_otp_max_attempts: int = 5
    password_reset_expire_minutes: int = 30
    oauth_state_expire_minutes: int = 10
    oauth_login_code_expire_minutes: int = 2
    ingestion_api_key: str | None = None

    # Optional Gemini-powered natural-language understanding for the shopping
    # assistant. Catalog facts and prices always continue to come from VEXTRO's
    # database; the model only classifies the request and extracts filters.
    assistant_ai_enabled: bool = False
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-3.5-flash-lite"

    # Scraper scheduler. The scheduler is a dedicated process so a crawl can
    # never block request handling; set ``scraper_autostart_with_api`` to
    # have the API launch it on startup during local development.
    scraper_enabled: bool = True
    scraper_run_on_startup: bool = True
    scraper_interval_hours: float = 12.0
    scraper_autostart_with_api: bool = False
    scraper_lock_path: str | None = None

    cors_origins: str = (
        "http://localhost:5173,http://127.0.0.1:5173"
    )

    frontend_base_url: str = "http://localhost:5173"
    api_public_base_url: str = "http://localhost:8000"

    google_oauth_client_id: str | None = None
    google_oauth_client_secret: str | None = None
    facebook_oauth_client_id: str | None = None
    facebook_oauth_client_secret: str | None = None

    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from_email: str | None = None
    smtp_from_name: str = "VEXTRO"
    smtp_use_tls: bool = True
    smtp_use_ssl: bool = False
    smtp_timeout_seconds: int = 15

    vapid_public_key: str | None = None
    vapid_private_key: str | None = None
    vapid_subject: str | None = None

    notification_delivery_max_attempts: int = 3

    digest_timezone: str = "Asia/Karachi"
    digest_daily_hour: int = 8
    digest_weekly_day: int = 0
    digest_weekly_hour: int = 9
    digest_attach_sme_report: bool = True
    digest_scheduler_enabled: bool = False
    notification_outbox_interval_seconds: int = 300

    @property
    def cors_origin_list(self) -> list[str]:
        """Return normalized configured frontend origins."""

        return [
            origin.strip()
            for origin in self.cors_origins.split(",")
            if origin.strip()
        ]

    @property
    def frontend_base_url_normalized(self) -> str:
        """Return the frontend base URL without a trailing slash."""

        return self.frontend_base_url.rstrip("/")

    @property
    def email_sender_address(self) -> str | None:
        """Return the configured envelope sender address."""

        return self.smtp_from_email or self.smtp_username

    @property
    def is_email_configured(self) -> bool:
        """Report whether SMTP delivery can be attempted."""

        return bool(
            self.smtp_host
            and self.email_sender_address
        )

    @property
    def is_web_push_configured(self) -> bool:
        """Report whether VAPID Web Push delivery can be attempted."""

        return bool(
            self.vapid_public_key
            and self.vapid_private_key
            and self.vapid_subject
        )

    @property
    def digest_zoneinfo(self) -> ZoneInfo:
        """Return the configured digest timezone, falling back to UTC."""

        try:
            return ZoneInfo(self.digest_timezone)
        except (ZoneInfoNotFoundError, ValueError):
            return ZoneInfo("UTC")

    model_config = SettingsConfigDict(
        env_file=(".env", "gemini.env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return the cached application settings."""

    return Settings()


settings = get_settings()
