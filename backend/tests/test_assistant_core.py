"""Unit tests for deterministic assistant intent handling."""

from app.services.assistant_service import detect_assistant_intent


def test_assistant_detects_supported_intents() -> None:
    assert detect_assistant_intent(
        "Compare Samsung A55 vs iPhone 15",
    ) == "comparison"
    assert detect_assistant_intent(
        "Should I buy now or wait?",
    ) == "buy_or_wait"
    assert detect_assistant_intent(
        "Alert me when Samsung reaches PKR 110000",
    ) == "set_price_alert"


def test_assistant_falls_back_to_product_search() -> None:
    assert detect_assistant_intent(
        "Show Samsung Galaxy A55",
    ) == "product_search"
