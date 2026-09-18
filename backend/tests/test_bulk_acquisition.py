"""Database-backed coverage for bounded listing bulk ingestion."""

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.price_history import PriceHistory
from app.models.product_listing import ProductListing
from app.schemas.acquisition import MAX_BULK_INGESTION_ITEMS
from tests.test_acquisition import (
    BASE_CAPTURE_TIME,
    ENDPOINT,
    acquisition_alert_context,
    acquisition_context,
    build_payload,
    configure_ingestion_key,
    ingestion_headers,
)


BULK_ENDPOINT = f"{ENDPOINT}/bulk"


def distinct_payloads(context: dict[str, object], count: int) -> list[dict]:
    items = []
    for index in range(count):
        item = build_payload(
            context,
            captured_at=BASE_CAPTURE_TIME + timedelta(minutes=index),
            current_price=120000 + index,
        )
        item["external_id"] = f"{context['external_id']}-bulk-{index}"
        item["product_url"] = (
            f"https://www.daraz.pk/products/bulk-{context['token']}-{index}"
        )
        items.append(item)
    return items


@pytest.mark.parametrize("headers", [{}, ingestion_headers("wrong-key")])
def test_bulk_requires_existing_ingestion_key(
    client: TestClient,
    acquisition_context: dict[str, object],
    headers: dict[str, str],
) -> None:
    response = client.post(
        BULK_ENDPOINT,
        headers=headers,
        json={"items": [build_payload(acquisition_context)]},
    )
    assert response.status_code == 401


@pytest.mark.parametrize(
    "items",
    [[], [{}] * (MAX_BULK_INGESTION_ITEMS + 1)],
)
def test_bulk_rejects_empty_and_oversized_requests(
    client: TestClient,
    items: list[dict],
) -> None:
    response = client.post(
        BULK_ENDPOINT,
        headers=ingestion_headers(),
        json={"items": items},
    )
    assert response.status_code == 422


def test_bulk_three_valid_items_create_three_histories(
    client: TestClient,
    database_session: Session,
    acquisition_context: dict[str, object],
) -> None:
    items = distinct_payloads(acquisition_context, 3)
    response = client.post(
        BULK_ENDPOINT,
        headers=ingestion_headers(),
        json={"items": items},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["received"] == 3
    assert body["succeeded"] == 3
    assert body["duplicates"] == body["rejected"] == body["failed"] == 0
    assert [result["status"] for result in body["results"]] == [
        "created", "created", "created",
    ]
    database_session.expire_all()
    listing_ids = [result["listing_id"] for result in body["results"]]
    assert database_session.scalar(
        select(func.count(PriceHistory.id)).where(
            PriceHistory.listing_id.in_(listing_ids)
        )
    ) == 3


def test_bulk_reuses_competitor_alert_evaluation(
    client: TestClient,
    acquisition_context: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[int] = []

    def record_competitor_evaluation(
        _session: Session,
        *,
        listing_id: int,
        competitor_price: object,
        currency: str,
    ) -> int:
        calls.append(listing_id)
        assert competitor_price == 120000
        assert currency == "PKR"
        return 2

    monkeypatch.setattr(
        "app.services.acquisition_service.evaluate_competitor_risk_alerts",
        record_competitor_evaluation,
    )
    item = distinct_payloads(acquisition_context, 1)[0]
    response = client.post(
        BULK_ENDPOINT,
        headers=ingestion_headers(),
        json={"items": [item]},
    )
    assert response.status_code == 200
    assert response.json()["results"][0]["competitor_alerts_triggered"] == 2
    assert len(calls) == 1


def test_bulk_mixed_results_alerts_history_and_retry_deduplication(
    client: TestClient,
    database_session: Session,
    acquisition_context: dict[str, object],
    acquisition_alert_context: dict[str, object],
) -> None:
    items = distinct_payloads(acquisition_context, 5)
    items[0]["current_price"] = 110000
    items[4]["product_variant_id"] = 999999999

    first = client.post(
        BULK_ENDPOINT,
        headers=ingestion_headers(),
        json={"items": items},
    )
    assert first.status_code == 200, first.text
    body = first.json()
    assert body["received"] == 5
    assert body["succeeded"] == 4
    assert body["duplicates"] == body["rejected"] == 0
    assert body["failed"] == 1
    assert [result["index"] for result in body["results"]] == list(range(5))
    assert body["results"][4]["status"] == "failed"
    assert body["results"][4]["error_code"] == "product_variant_not_found"
    assert sum(result["alerts_triggered"] for result in body["results"]) == 1

    database_session.expire_all()
    persisted_ids = [
        result["listing_id"]
        for result in body["results"]
        if result["listing_id"] is not None
    ]
    assert len(persisted_ids) == 4
    assert database_session.scalar(
        select(func.count(PriceHistory.id)).where(
            PriceHistory.listing_id.in_(persisted_ids)
        )
    ) == 4

    retry = client.post(
        BULK_ENDPOINT,
        headers=ingestion_headers(),
        json={"items": items},
    )
    assert retry.status_code == 200
    retry_body = retry.json()
    assert retry_body["succeeded"] == 0
    assert retry_body["duplicates"] == 4
    assert retry_body["failed"] == 1
    database_session.expire_all()
    assert database_session.scalar(
        select(func.count(PriceHistory.id)).where(
            PriceHistory.listing_id.in_(persisted_ids)
        )
    ) == 4


@pytest.mark.parametrize("invalid_price", [0, -1, "NaN", "Infinity", "abc123"])
def test_bulk_invalid_price_is_item_rejection_without_persistence(
    client: TestClient,
    database_session: Session,
    acquisition_context: dict[str, object],
    invalid_price: object,
) -> None:
    item = build_payload(acquisition_context)
    item["current_price"] = invalid_price
    response = client.post(
        BULK_ENDPOINT,
        headers=ingestion_headers(),
        json={"items": [item]},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["rejected"] == 1
    assert body["results"][0]["error_code"] == "invalid_listing_data"
    assert database_session.scalar(
        select(ProductListing.id).where(
            ProductListing.external_id == acquisition_context["external_id"]
        )
    ) is None
