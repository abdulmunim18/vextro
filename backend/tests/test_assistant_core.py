"""Unit tests for deterministic assistant intent handling."""

from types import SimpleNamespace

from app.services.assistant_service import (
    AssistantService,
    detect_assistant_intent,
    extract_assistant_entities,
    inherit_recommendation_context,
)
from app.repositories.assistant_repository import extract_camera_evidence
from app.repositories.assistant_repository import STOP_WORDS
from app.services.assistant_nlu_service import AssistantNLUResult


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


def test_assistant_understands_roman_urdu_buy_or_wait_question() -> None:
    assert detect_assistant_intent(
        "kya mujhe ye phone abhi lena chahiye?"
    ) == "buy_or_wait"


def test_explicit_comparison_does_not_add_old_context_product() -> None:
    oppo = SimpleNamespace(id=1, name="Oppo Mobile A6")
    samsung = SimpleNamespace(id=2, name="Samsung Mobile A07")
    old_context_product = SimpleNamespace(id=3, name="Club Mobile Grace")

    class ComparisonRepository:
        @staticmethod
        def find_product_entities(_database_session, _message):
            return [oppo, samsung]

        @staticmethod
        def get_products_by_ids(_database_session, _product_ids):
            return [old_context_product]

    service = AssistantService(repository=ComparisonRepository())
    resolved = service._resolve_products(
        None,
        message=(
            "Oppo Mobile A6, Samsung Mobile A07 in dono ka comparison "
            "aur price batao"
        ),
        intent="comparison",
        entities={},
        context={"product_ids": [3]},
    )

    assert [product.id for product in resolved] == [1, 2]


def test_assistant_parses_lakh_price_alert() -> None:
    entities = extract_assistant_entities(
        "1 lakh ke andar mobile recommend karo"
    )

    assert entities["budget_max"] == "100000"


def test_assistant_parses_typo_tolerant_roman_urdu_budget() -> None:
    message = "80 k andr muje phone recommend kro"

    assert detect_assistant_intent(message) == "recommendation"
    assert extract_assistant_entities(message)["budget_max"] == "80000"


def test_budget_before_category_is_still_a_recommendation() -> None:
    message = "60k k andr mobile dikhao"

    assert detect_assistant_intent(message) == "recommendation"
    assert extract_assistant_entities(message) == {
        "budget_max": "60000",
        "category": "Mobile Phones",
    }


def test_short_specification_follow_ups_extract_requested_field() -> None:
    assert detect_assistant_intent("ram") == "product_details"
    assert extract_assistant_entities("ram") == {
        "requested_fields": ["ram"],
    }


def test_generic_specification_words_are_not_product_name_terms() -> None:
    assert {"ram", "storage", "specs", "mobile", "phone"} <= STOP_WORDS


def test_gemini_result_maps_only_validated_catalog_entities() -> None:
    result = AssistantNLUResult(
        intent="recommendation",
        budget_max=60000,
        category="Mobile Phones",
        requested_fields=["ram"],
    )

    assert result.extracted_entities() == {
        "budget_max": "60000",
        "category": "Mobile Phones",
        "requested_fields": ["ram"],
    }


def test_assistant_uses_the_budget_next_to_under_phrase() -> None:
    message = "main ne kaha 80 k k andr tum ne 120k ka bataya"

    entities = extract_assistant_entities(message)

    assert entities["budget_max"] == "80000"


def test_assistant_understands_common_budget_formats() -> None:
    cases = {
        "100000 k budget main konsa mobile acha hoga": "100000",
        "100k budget mein phone suggest karo": "100000",
        "mera budget 100,000 hai mobile chahiye": "100000",
        "80 hazar tak phone recommend karo": "80000",
        "under PKR 90,000 mobile": "90000",
        "1 lakh budget mein mobile": "100000",
    }

    for message, expected in cases.items():
        assert extract_assistant_entities(message)["budget_max"] == expected


def test_budget_and_selection_questions_are_recommendations() -> None:
    messages = (
        "best phone under 80k",
        "mera budget 100000 hai mobile chahiye",
        "8GB RAM aur 256GB storage wala phone under 120k",
        "100000 k budget main konsa mobile achga hoga",
    )

    for message in messages:
        assert detect_assistant_intent(message) == "recommendation"


def test_assistant_recognizes_catalog_brand_and_smartphone_terms() -> None:
    assert extract_assistant_entities("Google smartphone under 150k") == {
        "budget_max": "150000",
        "category": "Mobile Phones",
        "brand": "Google",
    }


def test_assistant_detects_short_acknowledgement() -> None:
    assert detect_assistant_intent("ok tell") == "acknowledgement"


def test_assistant_understands_camera_quality_follow_up() -> None:
    message = "muje camera ki quality achi chahiye is k liye konsa best hoga"

    assert detect_assistant_intent(message) == "recommendation"
    assert extract_assistant_entities(message)["preference"] == "camera"


def test_recommendation_does_not_inherit_unrelated_brand_context() -> None:
    entities = {"category": "Mobile Phones", "preference": "camera"}
    context = {"last_intent": "lowest_price", "brand": "Samsung"}

    assert inherit_recommendation_context(entities, context) == entities


def test_recommendation_inherits_direct_budget_context() -> None:
    entities = {"preference": "camera"}
    context = {
        "last_intent": "recommendation",
        "budget_max": "80000",
        "category": "Mobile Phones",
    }

    assert inherit_recommendation_context(entities, context) == {
        "preference": "camera",
        "budget_max": "80000",
        "category": "Mobile Phones",
    }


def test_new_budget_resets_stale_recommendation_preferences() -> None:
    entities = {"budget_max": "100000", "category": "Mobile Phones"}
    context = {
        "last_intent": "recommendation",
        "budget_max": "80000",
        "category": "Mobile Phones",
        "brand": "Samsung",
        "preference": "camera",
    }

    assert inherit_recommendation_context(entities, context) == entities


def test_camera_evidence_does_not_invent_missing_specs() -> None:
    assert extract_camera_evidence({"color": "Black"}, "Apple iPhone 17") is None


def test_camera_evidence_separates_front_and_rear_values() -> None:
    evidence = extract_camera_evidence(
        {},
        "Phone - 32MP Front Camera - 200MP Rear Camera",
    )

    assert evidence == (200.0, 32.0, "listed 200MP rear/main + 32MP front")
