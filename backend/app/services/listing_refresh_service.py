"""Refresh one product's marketplace offers when a shopper opens it.

The scheduled crawl keeps the whole catalog fresh every few hours, which
still leaves a price up to one interval old. When a product page is opened
and its offers have not been confirmed recently, this service re-reads just
that product's marketplace pages, so the phone someone is actually looking
at shows the price the marketplace has now.

Nothing is parsed here. Each marketplace already has a spider that reads
its pages and delivers listings through the acquisition API; the refresh
runs that same spider for one product. Supporting another marketplace is
therefore one entry in :data:`TARGETED_SPIDERS`, provided its spider accepts
``-a product_urls=<url>[,<url>...]``.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.scraper_supervisor import SCRAPER_ROOT
from app.models.platform import Platform
from app.models.product_listing import ProductListing
from app.models.product_variant import ProductVariant
from app.schemas.listing_refresh import (
    PlatformRefreshStatus,
    ProductRefreshResponse,
)


logger = logging.getLogger(__name__)


# Marketplace code -> the spider that can re-read single product pages.
#
# A marketplace is listed only when one product page states its offers.
# Daraz is absent on purpose: its listing data comes from the category
# feed, and its product pages load prices through a signed request, so a
# single Daraz page cannot be refreshed. Daraz stays as fresh as the
# scheduled crawl, which takes about two minutes.
TARGETED_SPIDERS: dict[str, str] = {
    "priceoye": "priceoye_smartphones",
}

Launcher = Callable[[str, list[str]], object]


def launch_targeted_crawl(spider: str, product_urls: list[str]) -> object:
    """Start a spider for specific product pages without waiting for it."""

    environment = {
        **os.environ,
        "VEXTRO_SCRAPE_TRIGGER": "manual",
        "VEXTRO_API_URL": settings.on_demand_refresh_api_url
        or settings.api_public_base_url,
    }

    if settings.ingestion_api_key:
        environment["INGESTION_API_KEY"] = settings.ingestion_api_key

    return subprocess.Popen(
        [
            sys.executable,
            "-m",
            "scrapy",
            "crawl",
            spider,
            "-a",
            f"product_urls={','.join(product_urls)}",
            # Reviews change slowly and belong to the scheduled crawl; a
            # refresh is about the price on screen.
            "-s",
            "MAX_REVIEWS_PER_LISTING=0",
        ],
        cwd=SCRAPER_ROOT,
        env=environment,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


class ListingRefreshService:
    """Decide whether a product needs a refresh and start one."""

    def __init__(
        self,
        launcher: Launcher | None = None,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self.launcher = launcher or launch_targeted_crawl
        self.monotonic = monotonic
        # (product id, platform code) -> when a refresh was last started.
        self._started_at: dict[tuple[int, str], float] = {}
        self._running: list[object] = []

    def _running_count(self) -> int:
        self._running = [
            process
            for process in self._running
            if getattr(process, "poll", lambda: 0)() is None
        ]

        return len(self._running)

    @staticmethod
    def _same_site(product_url: str, base_url: str) -> bool:
        """Only a marketplace's own pages are ever handed to its spider."""

        page_host = (urlparse(product_url).hostname or "").removeprefix("www.")
        site_host = (urlparse(base_url).hostname or "").removeprefix("www.")

        return bool(page_host) and page_host == site_host

    def refresh_product(
        self,
        database_session: Session,
        product_id: int,
    ) -> ProductRefreshResponse:
        """Start a refresh for every stale, refreshable marketplace."""

        rows = database_session.execute(
            select(
                Platform.code,
                Platform.base_url,
                ProductListing.product_url,
                ProductListing.last_seen_at,
            )
            .join(Platform, Platform.id == ProductListing.platform_id)
            .join(
                ProductVariant,
                ProductVariant.id == ProductListing.product_variant_id,
            )
            .where(ProductVariant.canonical_product_id == product_id)
        ).all()

        by_platform: dict[str, dict[str, object]] = {}
        for code, base_url, product_url, last_seen_at in rows:
            entry = by_platform.setdefault(
                code,
                {"urls": [], "last_seen_at": None, "base_url": base_url},
            )
            if (
                product_url
                and product_url not in entry["urls"]
                and self._same_site(product_url, base_url)
            ):
                entry["urls"].append(product_url)
            if last_seen_at is not None and (
                entry["last_seen_at"] is None
                or last_seen_at > entry["last_seen_at"]
            ):
                entry["last_seen_at"] = last_seen_at

        now = datetime.now(UTC)
        max_age = timedelta(minutes=settings.on_demand_refresh_max_age_minutes)
        statuses: list[PlatformRefreshStatus] = []

        for code in sorted(by_platform):
            entry = by_platform[code]
            last_seen_at = entry["last_seen_at"]
            spider = TARGETED_SPIDERS.get(code)

            if not settings.on_demand_refresh_enabled:
                status = "disabled"
            elif spider is None or not entry["urls"]:
                status = "scheduled_only"
            elif last_seen_at is not None and now - last_seen_at <= max_age:
                status = "fresh"
            else:
                status = self._start(product_id, code, spider, entry["urls"])

            statuses.append(
                PlatformRefreshStatus(
                    platform_code=code,
                    status=status,
                    last_checked_at=last_seen_at,
                )
            )

        started = any(item.status == "started" for item in statuses)
        in_progress = any(item.status == "in_progress" for item in statuses)

        return ProductRefreshResponse(
            product_id=product_id,
            refreshing=started or in_progress,
            platforms=statuses,
            # How long the page should wait before reading the offers again.
            retry_after_seconds=(
                settings.on_demand_refresh_expected_seconds
                if started or in_progress
                else None
            ),
        )

    def _start(
        self,
        product_id: int,
        platform_code: str,
        spider: str,
        product_urls: list[str],
    ) -> str:
        key = (product_id, platform_code)
        started_at = self._started_at.get(key)
        now = self.monotonic()

        if (
            started_at is not None
            and now - started_at < settings.on_demand_refresh_cooldown_seconds
        ):
            # Someone opened this page a moment ago; one crawl serves both.
            return "in_progress"

        if self._running_count() >= settings.on_demand_refresh_max_parallel:
            return "busy"

        try:
            process = self.launcher(spider, product_urls)
        except OSError:
            logger.exception(
                "On-demand refresh could not start: product_id=%s "
                "platform=%s",
                product_id,
                platform_code,
            )
            return "failed"

        self._started_at[key] = now
        self._running.append(process)
        logger.info(
            "On-demand refresh started: product_id=%s platform=%s pages=%s",
            product_id,
            platform_code,
            len(product_urls),
        )

        return "started"


listing_refresh_service = ListingRefreshService()

__all__ = [
    "TARGETED_SPIDERS",
    "ListingRefreshService",
    "listing_refresh_service",
]
