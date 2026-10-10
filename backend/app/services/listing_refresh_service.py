"""Refresh one product's marketplace offers when a shopper opens it.

The scheduled crawl keeps the whole catalog fresh every few hours, which
still leaves a price up to one interval old, and a marketplace's listing
pages do not show everything it sells. When a product page is opened, this
service re-reads just that product on each marketplace, so the phone
someone is actually looking at shows what the marketplaces have now.

Nothing is parsed here. Each marketplace already has a spider that reads
its pages and delivers listings through the acquisition API; the refresh
runs that same spider for one product. Supporting another marketplace is
therefore one entry in :data:`TARGETED_SPIDERS`.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.scraper_supervisor import SCRAPER_ROOT
from app.models.canonical_product import CanonicalProduct
from app.models.platform import Platform
from app.models.product_listing import ProductListing
from app.models.product_variant import ProductVariant
from app.schemas.listing_refresh import (
    PlatformRefreshStatus,
    ProductRefreshResponse,
)


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TargetedSpider:
    """How one marketplace's spider is pointed at a single product.

    ``argument`` names the spider argument that narrows a run:

    * ``product_urls`` - re-read the product pages VEXTRO already holds
      listings for. Suits a marketplace whose product page states every
      offer, and needs at least one stored listing.
    * ``search_terms`` - look the phone up by name. Suits a marketplace
      whose offers come from a search or category feed, and also finds a
      phone VEXTRO has never seen there.
    """

    spider: str
    argument: str
    separator: str = ","


# Marketplace code -> how its spider refreshes one product. Adding a
# marketplace is one entry here, once its spider accepts the argument.
TARGETED_SPIDERS: dict[str, TargetedSpider] = {
    "priceoye": TargetedSpider("priceoye_smartphones", "product_urls"),
    "daraz": TargetedSpider("daraz_smartphones", "search_terms", "|"),
}

Launcher = Callable[[TargetedSpider, list[str]], object]


def launch_targeted_crawl(target: TargetedSpider, values: list[str]) -> object:
    """Start a spider for one product without waiting for it."""

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
            target.spider,
            "-a",
            f"{target.argument}={target.separator.join(values)}",
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
        """Start a refresh on every marketplace that needs one."""

        product_name = database_session.scalar(
            select(CanonicalProduct.name).where(
                CanonicalProduct.id == product_id,
                CanonicalProduct.is_active.is_(True),
            )
        )

        if product_name is None:
            return ProductRefreshResponse(
                product_id=product_id,
                refreshing=False,
            )

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
                {"urls": [], "last_seen_at": None},
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

        # A marketplace that is searched by name is asked even when VEXTRO
        # holds no listing there: that is how a phone it sells but never
        # showed in its listings is found.
        active_codes = set(
            database_session.scalars(
                select(Platform.code).where(Platform.is_active.is_(True))
            )
        )
        for code, target in TARGETED_SPIDERS.items():
            if target.argument == "search_terms" and code in active_codes:
                by_platform.setdefault(
                    code,
                    {"urls": [], "last_seen_at": None},
                )

        now = datetime.now(UTC)
        max_age = timedelta(minutes=settings.on_demand_refresh_max_age_minutes)
        statuses: list[PlatformRefreshStatus] = []

        for code in sorted(by_platform):
            entry = by_platform[code]
            last_seen_at = entry["last_seen_at"]
            target = TARGETED_SPIDERS.get(code)
            values = (
                []
                if target is None
                else [product_name]
                if target.argument == "search_terms"
                else entry["urls"]
            )

            if not settings.on_demand_refresh_enabled:
                status = "disabled"
            elif target is None or not values:
                status = "scheduled_only"
            elif last_seen_at is not None and now - last_seen_at <= max_age:
                status = "fresh"
            else:
                status = self._start(
                    product_id,
                    code,
                    target,
                    values,
                    # With no listing to date a lookup by, the lookup itself
                    # is what must not repeat within the freshness window.
                    cooldown_seconds=(
                        settings.on_demand_refresh_cooldown_seconds
                        if last_seen_at is not None
                        else max(
                            settings.on_demand_refresh_cooldown_seconds,
                            settings.on_demand_refresh_max_age_minutes * 60,
                        )
                    ),
                )

            statuses.append(
                PlatformRefreshStatus(
                    platform_code=code,
                    status=status,
                    last_checked_at=last_seen_at,
                )
            )

        refreshing = any(
            item.status in {"started", "in_progress"} for item in statuses
        )

        return ProductRefreshResponse(
            product_id=product_id,
            refreshing=refreshing,
            platforms=statuses,
            # How long the page should wait before reading the offers again.
            retry_after_seconds=(
                settings.on_demand_refresh_expected_seconds
                if refreshing
                else None
            ),
        )

    def _start(
        self,
        product_id: int,
        platform_code: str,
        target: TargetedSpider,
        values: list[str],
        *,
        cooldown_seconds: int,
    ) -> str:
        key = (product_id, platform_code)
        started_at = self._started_at.get(key)
        now = self.monotonic()

        if started_at is not None and now - started_at < cooldown_seconds:
            # Someone opened this page a moment ago and one crawl serves
            # both; later than that, the lookup has simply been done.
            return (
                "in_progress"
                if now - started_at
                < settings.on_demand_refresh_cooldown_seconds
                else "fresh"
            )

        if self._running_count() >= settings.on_demand_refresh_max_parallel:
            return "busy"

        try:
            process = self.launcher(target, values)
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
            "On-demand refresh started: product_id=%s platform=%s via %s",
            product_id,
            platform_code,
            target.argument,
        )

        return "started"


listing_refresh_service = ListingRefreshService()

__all__ = [
    "TARGETED_SPIDERS",
    "ListingRefreshService",
    "TargetedSpider",
    "listing_refresh_service",
]
