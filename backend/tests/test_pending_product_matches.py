from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.pending_product_match import PendingProductMatch
from app.models.product_listing import ProductListing
from tests.test_acquisition import (
    TEST_INGESTION_KEY,
    acquisition_context,
    build_payload,
    ingestion_headers,
)
from tests.test_admin_catalog import admin_headers


@pytest.fixture(autouse=True)
def configure_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ingestion_api_key", TEST_INGESTION_KEY)


def test_admin_can_resolve_replay_and_reuse_manual_match(
    client: TestClient,
    database_session: Session,
    acquisition_context: dict[str, object],
) -> None:
    external_id = f"pending-{uuid4().hex}"
    listing_payload = build_payload(acquisition_context)
    listing_payload.pop("product_variant_id")
    listing_payload["external_id"] = external_id
    listing_payload["product_url"] = (
        f"https://www.daraz.pk/products/{external_id}"
    )
    match_payload = {
        "platform_code": "daraz",
        "external_id": external_id,
        "title": listing_payload["title"],
        "brand": "Samsung",
        "model": None,
        "ram_gb": 8,
        "storage_gb": 256,
        "color": "Black",
    }

    queued = client.post(
        "/api/v1/internal/acquisition/pending-matches",
        headers=ingestion_headers(),
        json={
            "platform_code": "daraz",
            "external_id": external_id,
            "title": listing_payload["title"],
            "product_url": listing_payload["product_url"],
            "match_payload": match_payload,
            "listing_payload": listing_payload,
            "match_confidence": 61,
            "match_reason": "Automatic match was ambiguous.",
            "suggested_product_variant_id": acquisition_context["variant_id"],
        },
    )
    assert queued.status_code == 201, queued.text
    match_id = queued.json()["id"]

    headers = admin_headers(client, database_session)
    pending = client.get(
        "/api/v1/admin/pending-product-matches",
        params={"q": external_id},
        headers=headers,
    )
    assert pending.status_code == 200
    assert pending.json()["total_items"] == 1

    resolved = client.patch(
        f"/api/v1/admin/pending-product-matches/{match_id}/resolve",
        headers=headers,
        json={"product_variant_id": acquisition_context["variant_id"]},
    )
    assert resolved.status_code == 200, resolved.text
    assert resolved.json()["status"] == "resolved"

    reused = client.post(
        "/api/v1/internal/acquisition/match-product",
        headers=ingestion_headers(),
        json=match_payload,
    )
    assert reused.status_code == 200
    assert reused.json()["matched"] is True
    assert reused.json()["confidence"] == 100
    assert reused.json()["product_variant_id"] == acquisition_context["variant_id"]

    replayed = client.post(
        f"/api/v1/admin/pending-product-matches/{match_id}/replay",
        headers=headers,
    )
    assert replayed.status_code == 200, replayed.text
    assert replayed.json()["pending_match"]["status"] == "replayed"
    assert replayed.json()["ingestion"]["status"] == "created"

    database_session.expire_all()
    listing = database_session.scalar(
        select(ProductListing).where(ProductListing.external_id == external_id)
    )
    assert listing is not None
    assert listing.product_variant_id == acquisition_context["variant_id"]

    database_session.execute(
        delete(PendingProductMatch).where(PendingProductMatch.id == match_id)
    )
    database_session.commit()


def test_pending_match_admin_routes_reject_anonymous_user(
    client: TestClient,
) -> None:
    response = client.get("/api/v1/admin/pending-product-matches")
    assert response.status_code == 401


def test_admin_can_delete_pending_match(
    client: TestClient,
    database_session: Session,
    acquisition_context: dict[str, object],
) -> None:
    external_id = f"delete-pending-{uuid4().hex}"
    listing_payload = build_payload(acquisition_context)
    listing_payload.pop("product_variant_id")
    listing_payload["external_id"] = external_id
    listing_payload["product_url"] = (
        f"https://www.daraz.pk/products/{external_id}"
    )

    queued = client.post(
        "/api/v1/internal/acquisition/pending-matches",
        headers=ingestion_headers(),
        json={
            "platform_code": "daraz",
            "external_id": external_id,
            "title": listing_payload["title"],
            "product_url": listing_payload["product_url"],
            "match_payload": {
                "platform_code": "daraz",
                "external_id": external_id,
                "title": listing_payload["title"],
            },
            "listing_payload": listing_payload,
            "match_confidence": 20,
            "match_reason": "Not a catalog product.",
        },
    )
    assert queued.status_code == 201, queued.text
    match_id = queued.json()["id"]
    headers = admin_headers(client, database_session)

    deleted = client.delete(
        f"/api/v1/admin/pending-product-matches/{match_id}",
        headers=headers,
    )
    assert deleted.status_code == 204
    assert database_session.get(PendingProductMatch, match_id) is None

    missing = client.delete(
        f"/api/v1/admin/pending-product-matches/{match_id}",
        headers=headers,
    )
    assert missing.status_code == 404


def test_pending_match_delete_rejects_anonymous_user(
    client: TestClient,
) -> None:
    response = client.delete("/api/v1/admin/pending-product-matches/1")
    assert response.status_code == 401
