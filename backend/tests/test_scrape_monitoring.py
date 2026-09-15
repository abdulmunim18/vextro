from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.scrape_error import ScrapeError
from app.models.scrape_run import ScrapeRun


RUNS_ENDPOINT = "/api/v1/internal/acquisition/runs"
TEST_INGESTION_KEY = "VextroMonitoringTestKey2026Secure"


@pytest.fixture(autouse=True)
def configure_ingestion_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        settings,
        "ingestion_api_key",
        TEST_INGESTION_KEY,
    )


@pytest.fixture(autouse=True)
def clean_monitoring_records(
    database_session: Session,
) -> Generator[None, None, None]:
    yield
    database_session.rollback()
    database_session.execute(delete(ScrapeError))
    database_session.execute(delete(ScrapeRun))
    database_session.commit()


def headers(key: str = TEST_INGESTION_KEY) -> dict[str, str]:
    return {"X-Ingestion-Key": key}


def start_run(
    client: TestClient,
    *,
    platform: str = "daraz",
    spider_name: str = "daraz_smartphones",
) -> dict:
    response = client.post(
        RUNS_ENDPOINT,
        headers=headers(),
        json={
            "platform": platform,
            "spider_name": spider_name,
            "trigger_type": "test",
            "parser_version": f"{platform}-v1",
        },
    )
    assert response.status_code == 201
    return response.json()


def finish_run(
    client: TestClient,
    run_id: int,
    *,
    crawl_succeeded: bool,
    discovered: int,
    ingested: int,
    rejected: int,
    failed: int,
    errors: int,
):
    return client.patch(
        f"{RUNS_ENDPOINT}/{run_id}",
        headers=headers(),
        json={
            "crawl_succeeded": crawl_succeeded,
            "items_discovered": discovered,
            "items_ingested": ingested,
            "items_rejected": rejected,
            "items_failed": failed,
            "error_count": errors,
        },
    )


def test_run_lifecycle_finishes_completed(client: TestClient) -> None:
    run = start_run(client)
    assert run["status"] == "running"
    assert run["finished_at"] is None

    response = finish_run(
        client,
        run["id"],
        crawl_succeeded=True,
        discovered=0,
        ingested=0,
        rejected=0,
        failed=0,
        errors=0,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["finished_at"] is not None


def test_partial_run_persists_counters_and_related_errors(
    client: TestClient,
    database_session: Session,
) -> None:
    run = start_run(client)
    run_id = run["id"]

    success = client.post(
        f"{RUNS_ENDPOINT}/{run_id}/items/ingested",
        headers=headers(),
    )
    assert success.status_code == 200

    invalid_price = client.post(
        f"{RUNS_ENDPOINT}/{run_id}/errors",
        headers=headers(),
        json={
            "outcome": "rejected",
            "item_discovered": True,
            "external_listing_id": "daraz-invalid-price",
            "product_url": "https://www.daraz.pk/products/invalid",
            "error_type": "invalid_price",
            "error_stage": "validation",
            "message": "Marketplace price was invalid.",
            "raw_value": "'Call for Price'",
            "metadata": {},
        },
    )
    assert invalid_price.status_code == 201

    delivery_failure = client.post(
        f"{RUNS_ENDPOINT}/{run_id}/errors",
        headers=headers(),
        json={
            "outcome": "failed",
            "item_discovered": True,
            "external_listing_id": "daraz-timeout",
            "product_url": "https://www.daraz.pk/products/timeout",
            "error_type": "backend_timeout",
            "error_stage": "delivery",
            "message": "Secure acquisition timed out.",
            "metadata": {},
        },
    )
    assert delivery_failure.status_code == 201

    response = finish_run(
        client,
        run_id,
        crawl_succeeded=True,
        discovered=3,
        ingested=1,
        rejected=1,
        failed=1,
        errors=2,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "partial"
    assert body["items_discovered"] == 3
    assert body["items_ingested"] == 1
    assert body["items_rejected"] == 1
    assert body["items_failed"] == 1
    assert body["error_count"] == 2

    database_session.expire_all()
    saved_run = database_session.scalar(
        select(ScrapeRun).where(ScrapeRun.id == run_id)
    )
    assert saved_run is not None
    assert saved_run.status == "partial"

    errors = list(
        database_session.scalars(
            select(ScrapeError)
            .where(ScrapeError.scrape_run_id == run_id)
            .order_by(ScrapeError.id)
        ).all()
    )
    assert [error.error_type for error in errors] == [
        "invalid_price",
        "backend_timeout",
    ]


def test_failed_run_is_represented(client: TestClient) -> None:
    run = start_run(client)
    response = finish_run(
        client,
        run["id"],
        crawl_succeeded=False,
        discovered=0,
        ingested=0,
        rejected=0,
        failed=1,
        errors=1,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "failed"


def test_platform_runs_remain_independent(client: TestClient) -> None:
    daraz = start_run(client)
    priceoye = start_run(
        client,
        platform="priceoye",
        spider_name="priceoye_smartphones",
    )
    assert daraz["id"] != priceoye["id"]
    assert daraz["platform"] == "daraz"
    assert priceoye["platform"] == "priceoye"


@pytest.mark.parametrize("provided_headers", [{}, headers("wrong-key")])
def test_monitoring_routes_require_ingestion_key(
    client: TestClient,
    provided_headers: dict[str, str],
) -> None:
    response = client.post(
        RUNS_ENDPOINT,
        headers=provided_headers,
        json={
            "platform": "daraz",
            "spider_name": "daraz_smartphones",
            "trigger_type": "test",
            "parser_version": "daraz-v1",
        },
    )
    assert response.status_code == 401


def test_monitoring_redacts_sensitive_values(
    client: TestClient,
) -> None:
    run = start_run(client)
    response = client.post(
        f"{RUNS_ENDPOINT}/{run['id']}/errors",
        headers=headers(),
        json={
            "outcome": "failed",
            "item_discovered": False,
            "error_type": "spider_error",
            "error_stage": "parse",
            "message": f"Failure containing {TEST_INGESTION_KEY}",
            "metadata": {
                "authorization": TEST_INGESTION_KEY,
                "attempt": 2,
            },
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert TEST_INGESTION_KEY not in body["message"]
    assert body["error_metadata"]["authorization"] == "[REDACTED]"


def test_run_detail_returns_related_errors(client: TestClient) -> None:
    run = start_run(client)
    client.post(
        f"{RUNS_ENDPOINT}/{run['id']}/errors",
        headers=headers(),
        json={
            "outcome": "rejected",
            "error_type": "invalid_price",
            "error_stage": "validation",
            "message": "Invalid price",
        },
    )

    response = client.get(
        f"{RUNS_ENDPOINT}/{run['id']}",
        headers=headers(),
    )
    assert response.status_code == 200
    assert len(response.json()["errors"]) == 1
    assert response.json()["errors"][0]["error_type"] == "invalid_price"
