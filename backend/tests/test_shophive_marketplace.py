"""Shophive as a third marketplace."""

from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.platform import Platform
from app.services.listing_refresh_service import (
    TARGETED_SPIDERS,
    TargetedSpider,
)
from tests.test_listing_refresh import (  # noqa: F401 - shared fixtures
    RecordingLauncher,
    launcher,
    refresh,
    status_of,
)
from tests.test_smartphone_sync import (  # noqa: F401 - shared fixtures
    FIRST_CAPTURE,
    configure_ingestion_key,
    headers,
    ingest,
    listing_payload,
    read_listings,
    sync_context,
)


RUNS_ENDPOINT = "/api/v1/internal/acquisition/runs"
PENDING_ENDPOINT = "/api/v1/internal/acquisition/pending-matches"


# --------------------------------------------------------------------------
# The marketplace itself
# --------------------------------------------------------------------------


def test_shophive_is_a_registered_marketplace(
    database_session: Session,
) -> None:
    platform = database_session.scalar(
        select(Platform).where(Platform.code == "shophive")
    )

    assert platform is not None
    assert platform.is_active is True
    assert platform.name == "Shophive"


def test_a_shophive_offer_is_stored_beside_the_other_marketplaces(
    client: TestClient,
    database_session: Session,
    sync_context: dict[str, object],
) -> None:
    for platform_code, price in (
        ("priceoye", 144999),
        ("daraz", 149999),
        ("shophive", 141999),
    ):
        ingest(
            client,
            listing_payload(
                sync_context,
                current_price=price,
                captured_at=FIRST_CAPTURE,
                platform_code=platform_code,
                warranty="1 Year Manufacturer Warranty",
            ),
        )

    platform_ids = {
        platform.id: platform.code
        for platform in database_session.scalars(select(Platform))
    }
    prices = {
        platform_ids[item["platform_id"]]: float(item["current_price"])
        for item in read_listings(client, int(sync_context["product_id"]))
    }

    assert prices == {
        "priceoye": 144999.0,
        "daraz": 149999.0,
        "shophive": 141999.0,
    }


def test_a_shophive_crawl_is_tracked_like_any_other(client: TestClient) -> None:
    response = client.post(
        RUNS_ENDPOINT,
        headers=headers(),
        json={
            "platform": "shophive",
            "spider_name": "shophive_smartphones",
            "trigger_type": "test",
            "parser_version": "shophive-v1-storefront-feed",
        },
    )

    assert response.status_code == 201, response.text
    assert response.json()["platform"] == "shophive"


def test_an_unmatched_shophive_offer_can_wait_for_review(
    client: TestClient,
    sync_context: dict[str, object],
) -> None:
    external_id = f"U{uuid4().hex[:8]}"
    listing = listing_payload(
        sync_context,
        current_price=99999,
        captured_at=FIRST_CAPTURE,
        platform_code="shophive",
        external_id=external_id,
    )
    listing.pop("product_variant_id")

    response = client.post(
        PENDING_ENDPOINT,
        headers=headers(),
        json={
            "platform_code": "shophive",
            "external_id": external_id,
            "title": listing["title"],
            "product_url": listing["product_url"],
            "match_payload": {
                "platform_code": "shophive",
                "external_id": external_id,
                "title": listing["title"],
            },
            "listing_payload": listing,
            "match_confidence": 40,
            "match_reason": "No safe match.",
        },
    )

    assert response.status_code == 201, response.text


# --------------------------------------------------------------------------
# Refreshing one product
# --------------------------------------------------------------------------


def test_each_marketplace_says_how_its_spider_takes_one_product() -> None:
    assert TARGETED_SPIDERS["shophive"] == TargetedSpider(
        "shophive_smartphones",
        "product_urls",
    )


def test_opening_a_product_rereads_its_shophive_page(
    client: TestClient,
    sync_context: dict[str, object],
    launcher: RecordingLauncher,  # noqa: F811
) -> None:
    page = f"https://www.shophive.com/sync-phone-{sync_context['token']}/"
    ingest(
        client,
        listing_payload(
            sync_context,
            current_price=141999,
            captured_at=FIRST_CAPTURE,
            platform_code="shophive",
            product_url=page,
        ),
    )

    result = refresh(client, int(sync_context["product_id"]))

    assert status_of(result, "shophive") == "started"
    assert launcher.for_spider("shophive_smartphones") == [
        ("product_urls", [page]),
    ]
