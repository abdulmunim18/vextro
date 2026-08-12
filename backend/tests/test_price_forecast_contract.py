from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.models.price_forecast import PriceForecast
from app.schemas.price_intelligence import PriceForecastPublishRequest
from app.services.price_intelligence_service import _build_price_forecast_response


def valid_payload() -> dict[str, object]:
    return {
        "product_variant_id": 1,
        "model_name": "ARIMA",
        "model_version": "price-arima-v1",
        "horizon_days": 2,
        "currency": "pkr",
        "training_observation_count": 30,
        "training_started_at": "2026-06-01T00:00:00Z",
        "training_ended_at": "2026-07-30T00:00:00Z",
        "mae": "950.25",
        "rmse": "1210.40",
        "mape": "1.18",
        "confidence": "medium",
        "forecast": [
            {"forecast_date": "2026-08-13", "predicted_price": "111500.00"},
            {"forecast_date": "2026-08-14", "predicted_price": "111000.00"},
        ],
        "limitations": ["Marketplace promotions can change prices quickly."],
        "generated_at": "2026-08-12T15:00:00Z",
    }


def test_forecast_publish_contract_normalizes_valid_payload() -> None:
    payload = PriceForecastPublishRequest.model_validate(valid_payload())

    assert payload.currency == "PKR"
    assert payload.horizon_days == len(payload.forecast)
    assert payload.forecast[0].forecast_date == date(2026, 8, 13)


def test_forecast_contract_rejects_horizon_mismatch() -> None:
    data = valid_payload()
    data["horizon_days"] = 3

    with pytest.raises(ValidationError, match="horizon_days"):
        PriceForecastPublishRequest.model_validate(data)


def test_forecast_contract_requires_metrics_and_limitations() -> None:
    no_metrics = valid_payload()
    no_metrics["mae"] = None
    no_metrics["rmse"] = None
    no_metrics["mape"] = None

    with pytest.raises(ValidationError, match="evaluation metric"):
        PriceForecastPublishRequest.model_validate(no_metrics)

    no_limitations = valid_payload()
    no_limitations["limitations"] = []

    with pytest.raises(ValidationError, match="at least 1 item"):
        PriceForecastPublishRequest.model_validate(no_limitations)


def test_forecast_contract_rejects_duplicate_or_unordered_dates() -> None:
    duplicate_data = valid_payload()
    duplicate_data["forecast"] = [
        {"forecast_date": "2026-08-13", "predicted_price": "111500.00"},
        {"forecast_date": "2026-08-13", "predicted_price": "111000.00"},
    ]

    with pytest.raises(ValidationError, match="unique"):
        PriceForecastPublishRequest.model_validate(duplicate_data)

    unordered_data = valid_payload()
    unordered_data["forecast"] = list(reversed(unordered_data["forecast"]))

    with pytest.raises(ValidationError, match="ordered"):
        PriceForecastPublishRequest.model_validate(unordered_data)


def test_public_response_preserves_model_provenance_and_metrics() -> None:
    forecast = PriceForecast(
        id=42,
        product_variant_id=7,
        model_name="ARIMA",
        model_version="price-arima-v1",
        horizon_days=2,
        currency="PKR",
        training_observation_count=30,
        training_started_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
        training_ended_at=datetime(2026, 7, 30, tzinfo=timezone.utc),
        mae=Decimal("950.25"),
        rmse=Decimal("1210.40"),
        mape=Decimal("1.18"),
        confidence="medium",
        forecast_points=[
            {"forecast_date": "2026-08-13", "predicted_price": "111500.00"},
            {"forecast_date": "2026-08-14", "predicted_price": "111000.00"},
        ],
        limitations=["Promotions are not known in advance."],
        generated_at=datetime(2026, 8, 12, 15, tzinfo=timezone.utc),
        is_active=True,
    )

    response = _build_price_forecast_response(3, "Galaxy A55", forecast)

    assert response.status == "available"
    assert response.forecast_id == 42
    assert response.model_version == "price-arima-v1"
    assert response.mae == Decimal("950.25")
    assert response.forecast[-1].predicted_price == Decimal("111000.00")


def test_public_response_is_honest_when_no_forecast_exists() -> None:
    response = _build_price_forecast_response(3, "Galaxy A55", None)

    assert response.status == "insufficient_data"
    assert response.forecast == []
    assert response.model_version is None
    assert response.limitations
