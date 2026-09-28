"""Unit tests for deterministic assistant intent handling."""

from app.services.assistant_service import (
    detect_assistant_intent,
    extract_assistant_entities,
)


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


def test_assistant_understands_roman_urdu_and_budget() -> None:
    message = "Samsung ka 80k ke andar 8GB RAM wala phone recommend karo"

    assert detect_assistant_intent(message) == "recommendation"
    assert extract_assistant_entities(message) == {
        "budget_max": "80000",
        "category": "Mobile Phones",
        "brand": "Samsung",
        "ram_gb": 8,
    }


def test_assistant_understands_contextual_product_questions() -> None:
    assert detect_assistant_intent("is ki RAM kitni hai?") == "product_details"
    assert extract_assistant_entities("dusre wale ki history dikhao") == {
        "reference": "second",
    }


def test_assistant_parses_lakh_price_alert() -> None:
    entities = extract_assistant_entities(
        "1 lakh ke andar mobile recommend karo"
    )

    assert entities["budget_max"] == "100000"
