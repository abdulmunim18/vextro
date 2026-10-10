"""Refreshing one product's offers when its page is opened."""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.services.listing_refresh_service import (
    TARGETED_SPIDERS,
    TargetedSpider,
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
        self.calls: list[tuple[str, str, list[str]]] = []

    def __call__(self, target: TargetedSpider, values: list[str]) -> object:
        self.calls.append((target.spider, target.argument, list(values)))
        return self.Process()

    def for_spider(self, spider: str) -> list[tuple[str, list[str]]]:
        return [
            (argument, values)
            for name, argument, values in self.calls
            if name == spider
        ]


@pytest.fixture
def launcher(monkeypatch: pytest.MonkeyPatch) -> RecordingLauncher:
    """Route refreshes to a recorder and start each test with no history."""

    recorder = RecordingLauncher()
    monkeypatch.setattr(listing_refresh_service, "launcher", recorder)
    monkeypatch.setattr(listing_refresh_service, "_started_at", {})
    monkeypatch.setattr(listing_refresh_service, "_running", [])
    monkeypatch.setattr(settings, "on_demand_refresh_enabled", True)
    monkeypatch.setattr(settings, "on_demand_refresh_max_parallel", 5)

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


def test_opening_a_product_with_old_prices_rereads_its_marketplace_page(
    client: TestClient,
    sync_context: dict[str, object],
    launcher: RecordingLauncher,
) -> None:
    """A price confirmed days ago is re-read; the catalogue is not crawled."""

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
    assert launcher.for_spider("priceoye_smartphones") == [
        (
            "product_urls",
            [f"https://www.priceoye.pk/products/sync-{sync_context['token']}"],
        ),
    ]


def test_a_phone_with_no_daraz_listing_is_looked_up_on_daraz_by_name(
    client: TestClient,
    sync_context: dict[str, object],
    launcher: RecordingLauncher,
) -> None:
    """Daraz sells phones its listing pages never show; a search finds them."""

    capture(
        client,
        sync_context,
        platform_code="priceoye",
        captured_at=datetime.now(timezone.utc) - timedelta(minutes=5),
    )

    result = refresh(client, int(sync_context["product_id"]))

    assert status_of(result, "priceoye") == "fresh"
    assert status_of(result, "daraz") == "started"
    assert launcher.for_spider("daraz_smartphones") == [
        ("search_terms", [sync_context["product_name"]]),
    ]
    assert launcher.for_spider("priceoye_smartphones") == []


def test_a_lookup_that_found_nothing_is_not_repeated_on_every_visit(
    client: TestClient,
    sync_context: dict[str, object],
    launcher: RecordingLauncher,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A phone Daraz does not sell is asked about once per freshness window."""

    clock = {"now": 1000.0}
    monkeypatch.setattr(
        listing_refresh_service,
        "monotonic",
        lambda: clock["now"],
    )
    product_id = int(sync_context["product_id"])
    capture(
        client,
        sync_context,
        platform_code="priceoye",
        captured_at=datetime.now(timezone.utc) - timedelta(minutes=5),
    )

    first = refresh(client, product_id)
    clock["now"] += 30
    moments_later = refresh(client, product_id)
    clock["now"] += 20 * 60
    twenty_minutes_later = refresh(client, product_id)
    clock["now"] += 60 * 60
    over_an_hour_later = refresh(client, product_id)

    assert status_of(first, "daraz") == "started"
    assert status_of(moments_later, "daraz") == "in_progress"
    assert moments_later["refreshing"] is True
    assert status_of(twenty_minutes_later, "daraz") == "fresh"
    assert twenty_minutes_later["refreshing"] is False
    assert status_of(over_an_hour_later, "daraz") == "started"
    assert len(launcher.for_spider("daraz_smartphones")) == 2


def test_recently_confirmed_offers_are_left_alone(
    client: TestClient,
    sync_context: dict[str, object],
    launcher: RecordingLauncher,
) -> None:
    recently = datetime.now(timezone.utc) - timedelta(minutes=5)
    capture(client, sync_context, platform_code="priceoye", captured_at=recently)
    capture(client, sync_context, platform_code="daraz", captured_at=recently)

    result = refresh(client, int(sync_context["product_id"]))

    assert result["refreshing"] is False
    assert status_of(result, "priceoye") == "fresh"
    assert status_of(result, "daraz") == "fresh"
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
    assert len(launcher.for_spider("priceoye_smartphones")) == 1


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


def test_an_unknown_product_starts_nothing(
    client: TestClient,
    launcher: RecordingLauncher,
) -> None:
    result = refresh(client, 999_999_999)

    assert result["refreshing"] is False
    assert result["platforms"] == []
    assert launcher.calls == []


def test_each_marketplace_says_how_its_spider_takes_one_product() -> None:
    """Adding a marketplace is one entry here plus a spider that honours it."""

    assert TARGETED_SPIDERS == {
        "priceoye": TargetedSpider("priceoye_smartphones", "product_urls"),
        "daraz": TargetedSpider("daraz_smartphones", "search_terms", "|"),
    }
