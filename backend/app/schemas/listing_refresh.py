"""Contracts for refreshing one product's marketplace offers on demand."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


# started        a refresh was launched for this request
# in_progress    one was launched moments ago and is still running
# fresh          the offers were confirmed recently enough
# scheduled_only this marketplace cannot be refreshed one product at a time
# busy           too many refreshes are running; the scheduled crawl covers it
# disabled       on-demand refresh is switched off
# failed         the refresh could not be started
RefreshStatus = Literal[
    "started",
    "in_progress",
    "fresh",
    "scheduled_only",
    "busy",
    "disabled",
    "failed",
]


class PlatformRefreshStatus(BaseModel):
    platform_code: str
    status: RefreshStatus
    last_checked_at: datetime | None = None


class ProductRefreshResponse(BaseModel):
    product_id: int
    refreshing: bool
    platforms: list[PlatformRefreshStatus] = Field(default_factory=list)
    retry_after_seconds: int | None = None
