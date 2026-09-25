import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_get_warehouse_metrics():
    response = client.get("/api/v1/warehouse/metrics")
    assert response.status_code == 200
    data = response.json()
    assert "canonical_products_count" in data
    assert "product_listings_count" in data
    assert "price_history_observations_count" in data
    assert "platform_summary" in data
    assert "data_health" in data


def test_scrape_run_lifecycle():
    # 1. Start a scrape run
    start_res = client.post(
        "/api/v1/warehouse/scrape-runs/start",
        json={"platform": "PriceOyeTest", "triggered_by": "MANUAL"},
    )
    assert start_res.status_code == 201
    run_data = start_res.json()
    run_id = run_data["id"]
    assert run_data["status"] == "RUNNING"
    assert run_data["platform"] == "PriceOyeTest"

    # 2. Finish the scrape run
    finish_res = client.post(
        f"/api/v1/warehouse/scrape-runs/{run_id}/finish",
        json={
            "status": "SUCCESS",
            "items_scraped": 25,
            "items_failed": 0,
            "error_message": None,
        },
    )
    assert finish_res.status_code == 200
    finished_data = finish_res.json()
    assert finished_data["status"] == "SUCCESS"
    assert finished_data["items_scraped"] == 25

    # 3. Verify in scrape runs list
    list_res = client.get("/api/v1/warehouse/scrape-runs?limit=10")
    assert list_res.status_code == 200
    runs = list_res.json()
    assert any(r["id"] == run_id for r in runs)


def test_warehouse_data_audit():
    audit_res = client.post("/api/v1/warehouse/maintenance/audit")
    assert audit_res.status_code == 200
    report = audit_res.json()
    assert "health_score_percentage" in report
    assert "total_canonical_products" in report
    assert report["status"] in ["HEALTHY", "DEGRADED"]
