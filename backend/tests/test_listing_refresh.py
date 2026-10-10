"""Refreshing one product's offers when its page is opened."""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.services.listing_refresh_service import (
    TARGETED_SPIDERS,
    listing_refresh_service,
)
from tests.test_smartphone_sync import (  # noqa: F401 - shared fixtures
    FIRST_CAPTURE,
    configure_ingestion_key,
    ingest,
    listing_payload,
    sync_context,
)


class RecordingLauncher:
    """Stands in for the spider subprocess a refresh would start."""

    class Process:
        def poll(self) -> int | None:
            return None

    def __init__(self) -> None:
        self.calls: list[tuple[str, list[str]]] = []

    def __call__(self, spider: str, product_urls: list[str]) -> object:
        self.calls.append((spider, list(product_urls)))
        return self.Process()


@pytest.fixture
def launcher(monkeypatch: pytest.MonkeyPatch) -> RecordingLauncher:
    """Route refreshes to a recorder and start each test with no history."""

    recorder = RecordingLauncher()
    monkeypatch.setattr(listing_refresh_service, "launcher", recorder)
    monkeypatch.setattr(listing_refresh_service, "_started_at", {})
    monkeypatch.setattr(listing_refresh_service, "_running", [])
    monkeypatch.setattr(settings, "on_demand_refresh_enabled", True)

    return recorder


def refresh(client: TestClient, product_id: int) -> dict[str, object]:
    response = client.post(f"/api/v1/products/{product_id}/refresh")
    assert response.status_code == 200, response.text
    return response.json()


def status_of(result: dict[str, object], platform_code: str) -> str:
    return next(
        item["status"]
        for item in result["platforms"]
        if item["platform_code"] == platform_code
    )


def capture(client, context, *, platform_code, captured_at):
    ingest(
        client,
        listing_payload(
            context,
            current_price=144999,
            captured_at=captured_at,
            platform_code=platform_code,
        ),
    )


def test_opening_a_product_with_old_prices_refreshes_only_that_product(
    client: TestClient,
    sync_context: dict[str, object],
    launcher: RecordingLauncher,
) -> None:
    """A price confirmed days ago is re-read; nothing else is crawled."""

    capture(
        client,
        sync_context,
        platform_code="priceoye",
        captured_at=FIRST_CAPTURE,
    )

    result = refresh(client, int(sync_context["product_id"]))

    assert result["refreshing"] is True
    assert status_of(result, "priceoye") == "started"
    assert result["retry_after_seconds"] > 0
    assert launcher.calls == [
        (
            "priceoye_smartphones",
            [f"https://www.priceoye.pk/products/sync-{sync_context['token']}"],
        ),
    ]


def test_a_recently_confirmed_price_is_not_refreshed_again(
    client: TestClient,
    sync_context: dict[str, object],
    launcher: RecordingLauncher,
) -> None:
    capture(
        client,
        sync_context,
        platform_code="priceoye",
        captured_at=datetime.now(timezone.utc) - timedelta(minutes=5),
    )

    result = refresh(client, int(sync_context["product_id"]))

    assert result["refreshing"] is False
    assert status_of(result, "priceoye") == "fresh"
    assert launcher.calls == []


def test_one_refresh_serves_everyone_who_opens_the_page_meanwhile(
    client: TestClient,
    sync_context: dict[str, object],
    launcher: RecordingLauncher,
) -> None:
    capture(
        client,
        sync_context,
        platform_code="priceoye",
        captured_at=FIRST_CAPTURE,
    )
    product_id = int(sync_context["product_id"])

    first = refresh(client, product_id)
    second = refresh(client, product_id)

    assert status_of(first, "priceoye") == "started"
    assert status_of(second, "priceoye") == "in_progress"
    assert second["refreshing"] is True
    assert len(launcher.calls) == 1


def test_a_marketplace_without_a_single_page_refresh_waits_for_the_crawl(
    client: TestClient,
    sync_context: dict[str, object],
    launcher: RecordingLauncher,
) -> None:
    """Daraz offers come from its category feed, not from a product page."""

    capture(
        client,
        sync_context,
        platform_code="daraz",
        captured_at=FIRST_CAPTURE,
    )

    result = refresh(client, int(sync_context["product_id"]))

    assert result["refreshing"] is False
    assert status_of(result, "daraz") == "scheduled_only"
    assert launcher.calls == []


def test_refreshes_are_capped_so_a_busy_site_cannot_flood_a_marketplace(
    client: TestClient,
    sync_context: dict[str, object],
    launcher: RecordingLauncher,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "on_demand_refresh_max_parallel", 1)
    # Another product's refresh is still running.
    monkeypatch.setattr(
        listing_refresh_service,
        "_running",
        [RecordingLauncher.Process()],
    )
    capture(
        client,
        sync_context,
        platform_code="priceoye",
        captured_at=FIRST_CAPTURE,
    )

    result = refresh(client, int(sync_context["product_id"]))

    assert status_of(result, "priceoye") == "busy"
    assert launcher.calls == []


def test_switching_the_feature_off_starts_nothing(
    client: TestClient,
    sync_context: dict[str, object],
    launcher: RecordingLauncher,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "on_demand_refresh_enabled", False)
    capture(
        client,
        sync_context,
        platform_code="priceoye",
        captured_at=FIRST_CAPTURE,
    )

    result = refresh(client, int(sync_context["product_id"]))

    assert status_of(result, "priceoye") == "disabled"
    assert launcher.calls == []


def test_every_refreshable_marketplace_names_a_spider() -> None:
    """Adding a marketplace is one entry here plus a spider that honours it."""

    assert TARGETED_SPIDERS == {"priceoye": "priceoye_smartphones"}
