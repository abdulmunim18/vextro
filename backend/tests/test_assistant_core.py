"""Unit tests for deterministic assistant intent handling."""

from types import SimpleNamespace

from app.services.assistant_service import (
    AssistantService,
    _extract_target_price,
    detect_assistant_intent,
    extract_assistant_entities,
    inherit_pending_entities,
    inherit_recommendation_context,
    is_grounded_catalog_request,
    is_named_product_comparison,
    latest_grounding_timestamp,
    reconcile_assistant_intent,
)
from app.repositories.assistant_repository import (
    AssistantRepository,
    STOP_WORDS,
    extract_camera_evidence,
    extract_processor_evidence,
    product_search_terms,
    rank_product_entity_matches,
)
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


def test_assistant_rejects_obviously_unrelated_questions() -> None:
    unrelated_messages = (
        "What is today's weather?",
        "Teach me Python programming",
        "Who won the cricket match?",
        "Aaj mujhe algebra sikha do",
    )

    for message in unrelated_messages:
        assert detect_assistant_intent(message) == "out_of_scope"


def test_help_with_an_unrelated_topic_is_not_a_greeting() -> None:
    assert detect_assistant_intent("Help me write an essay") == "out_of_scope"
    assert detect_assistant_intent("help") == "greeting"


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
    assert extract_assistant_entities("pichle dono ko compare kro") == {
        "reference": "previous_two",
    }


def test_assistant_extracts_numbered_comparison_choices() -> None:
    assert extract_assistant_entities("1 and 2") == {
        "selection_indices": [1, 2],
    }
    assert extract_assistant_entities("1 2 ko compare kro") == {
        "selection_indices": [1, 2],
    }
    assert extract_assistant_entities("pehla aur doosra compare karo") == {
        "selection_indices": [1, 2],
    }
    assert extract_assistant_entities("1") == {
        "selection_indices": [1],
    }


def test_exact_product_matching_excludes_unrequested_variants() -> None:
    products = [
        SimpleNamespace(id=1, name="VIVO Y83", model="VIVO Y83"),
        SimpleNamespace(id=2, name="Vivo V70", model="Vivo V70"),
        SimpleNamespace(id=3, name="vivo V70 FE", model="vivo V70 FE"),
        SimpleNamespace(id=4, name="Vivo Y05", model="Vivo Y05"),
    ]

    matched = rank_product_entity_matches(
        "vivo y83 or vivo v70 ka comparison kro",
        products,
    )

    assert [product.id for product in matched] == [1, 2]


def test_exact_product_matching_prefers_specific_iphone_model() -> None:
    products = [
        SimpleNamespace(id=1, name="Apple iPhone 17", model="Apple iPhone 17"),
        SimpleNamespace(
            id=2,
            name="Apple iPhone 17 Pro",
            model="Apple iPhone 17 Pro",
        ),
        SimpleNamespace(
            id=3,
            name="Apple iPhone 17 Pro Max",
            model="Apple iPhone 17 Pro Max",
        ),
        SimpleNamespace(
            id=4,
            name="Apple iPhone 17 Air",
            model="Apple iPhone 17 Air",
        ),
    ]

    matched = rank_product_entity_matches(
        "what is the price of iphone 17 pro",
        products,
    )

    assert [product.id for product in matched] == [2]


def test_comparison_carries_iphone_family_to_second_numeric_model() -> None:
    products = [
        SimpleNamespace(
            id=1,
            name="Apple iPhone 18 Pro Max",
            model="Apple iPhone 18 Pro Max",
        ),
        SimpleNamespace(
            id=2,
            name="Apple Iphone 17 Pro Max",
            model="Apple Iphone 17 Pro Max",
        ),
        SimpleNamespace(
            id=3,
            name="Apple iPhone 10 Pro Max",
            model="Apple iPhone 10 Pro Max",
        ),
    ]

    matched = rank_product_entity_matches(
        "iphone 18 pro max or 17 pro max ko compare kro all aspects se",
        products,
    )

    assert [product.id for product in matched] == [1, 2]
    assert "reference" not in extract_assistant_entities(
        "iphone 18 pro max or 17 pro max ko compare kro all aspects se"
    )


def test_exact_product_matching_drops_model_contained_in_longer_model() -> None:
    products = [
        SimpleNamespace(
            id=1,
            name="Itel Super S26 Ultra",
            model="Itel Super S26 Ultra",
        ),
        SimpleNamespace(
            id=2,
            name="Itel S26 Ultra",
            model="Itel S26 Ultra",
        ),
    ]

    single_match = rank_product_entity_matches(
        "kya main itel super s26 ultra abhi buy kroon ya nhi",
        products,
    )
    separate_matches = rank_product_entity_matches(
        "Itel Super S26 Ultra or Itel S26 Ultra",
        products,
    )

    assert [product.id for product in single_match] == [1]
    assert [product.id for product in separate_matches] == [1, 2]


def test_assistant_understands_roman_urdu_buy_or_wait_question() -> None:
    assert detect_assistant_intent(
        "kya mujhe ye phone abhi lena chahiye?"
    ) == "buy_or_wait"
    assert detect_assistant_intent(
        "kya main itel super s26 ultra abhi buy kroon ya nhi price k hissab se"
    ) == "buy_or_wait"


def test_named_camera_question_is_a_product_comparison() -> None:
    assert is_named_product_comparison(
        "Infinix Hot 60 Pro Redmi Note 15 4G in these 2 which have best camera",
        2,
    ) is True
    assert is_named_product_comparison("best camera phone under 80k", 0) is False
    assert is_named_product_comparison("which one has the best camera?", 2) is True


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


def test_previous_two_comparison_uses_only_two_recent_products() -> None:
    products = [
        SimpleNamespace(id=1, name="Phone One"),
        SimpleNamespace(id=2, name="Phone Two"),
        SimpleNamespace(id=3, name="Phone Three"),
        SimpleNamespace(id=4, name="Phone Four"),
    ]

    class Repository:
        @staticmethod
        def find_product_entities(*_args, **_kwargs):
            return []

        @staticmethod
        def get_products_by_ids(*_args, **_kwargs):
            return products

    service = AssistantService(repository=Repository())
    resolved = service._resolve_products(
        None,
        message="pichle dono ko compare kro",
        intent="comparison",
        entities={"reference": "previous_two"},
        context={"product_ids": [1, 2, 3, 4]},
        explicit_products=[],
    )

    assert [product.id for product in resolved] == [1, 2]


def test_explicit_product_replaces_stale_selected_product() -> None:
    iphone = SimpleNamespace(id=244, name="Apple iPhone 17 Pro")
    stale_samsung = SimpleNamespace(id=77, name="Samsung A57")

    class ProductRepository:
        @staticmethod
        def find_product_entities(_database_session, _message):
            return [iphone]

        @staticmethod
        def get_products_by_ids(_database_session, _product_ids):
            return [stale_samsung]

    service = AssistantService(repository=ProductRepository())
    resolved = service._resolve_products(
        None,
        message="what is the price of iphone 17 pro",
        intent="lowest_price",
        entities={"brand": "Apple"},
        context={"product_ids": [77], "selected_product_id": 77},
    )

    assert [product.id for product in resolved] == [244]


def test_numbered_follow_up_uses_only_pending_comparison_choices() -> None:
    products = {
        1: SimpleNamespace(id=1, name="VIVO Y83"),
        2: SimpleNamespace(id=2, name="Vivo V70"),
        3: SimpleNamespace(id=3, name="vivo V70 FE"),
        99: SimpleNamespace(id=99, name="Old unrelated product"),
    }

    class ComparisonRepository:
        @staticmethod
        def find_product_entities(_database_session, _message):
            return []

        @staticmethod
        def get_products_by_ids(_database_session, product_ids):
            return [products[product_id] for product_id in product_ids]

    service = AssistantService(repository=ComparisonRepository())
    resolved = service._resolve_products(
        None,
        message="1 and 2",
        intent="comparison",
        entities={"selection_indices": [1, 2]},
        context={
            "product_ids": [99, 1, 2, 3],
            "comparison_product_ids": [1, 2, 3],
        },
    )

    assert [product.id for product in resolved] == [1, 2]


def test_single_number_resolves_pending_single_product_question() -> None:
    products = {
        1: SimpleNamespace(id=1, name="Itel Super S26 Ultra"),
        2: SimpleNamespace(id=2, name="Itel S26 Ultra"),
    }

    class ChoiceRepository:
        @staticmethod
        def find_product_entities(_database_session, _message):
            return []

        @staticmethod
        def get_products_by_ids(_database_session, product_ids):
            return [products[product_id] for product_id in product_ids]

    service = AssistantService(repository=ChoiceRepository())
    resolved = service._resolve_products(
        None,
        message="1",
        intent="buy_or_wait",
        entities={"selection_indices": [1]},
        context={
            "pending_intent": "buy_or_wait",
            "pending_product_ids": [1, 2],
            "product_ids": [2, 1],
        },
    )

    assert [product.id for product in resolved] == [1]


def test_single_named_comparison_does_not_pull_stale_context_without_reference() -> None:
    vivo = SimpleNamespace(id=1, name="Vivo V70")
    stale_product = SimpleNamespace(id=2, name="Old unrelated product")

    class ComparisonRepository:
        @staticmethod
        def find_product_entities(_database_session, _message):
            return [vivo]

        @staticmethod
        def get_products_by_ids(_database_session, _product_ids):
            return [stale_product]

    service = AssistantService(repository=ComparisonRepository())
    resolved = service._resolve_products(
        None,
        message="compare Vivo V70",
        intent="comparison",
        entities={},
        context={"product_ids": [2]},
    )

    assert [product.id for product in resolved] == [1]


def test_single_product_intent_does_not_silently_pick_first_context_item() -> None:
    service = AssistantService()
    products = [
        SimpleNamespace(id=1, name="VIVO Y83", model="VIVO Y83"),
        SimpleNamespace(id=2, name="Vivo V70", model="Vivo V70"),
    ]

    answer, grounded_data = service._build_answer(
        None,
        user_id=1,
        intent="lowest_price",
        message="price batao",
        products=products,
        entities={},
    )

    assert answer.startswith("Which product do you mean?")
    assert grounded_data["needs_clarification"] is True


def test_comparison_without_available_offers_never_renders_none(
    monkeypatch,
) -> None:
    products = [
        SimpleNamespace(id=1, name="Phone One", model="One"),
        SimpleNamespace(id=2, name="Phone Two", model="Two"),
    ]
    comparison = SimpleNamespace(
        total=2,
        summary=SimpleNamespace(
            cheapest_product_name=None,
            lowest_current_price=None,
            price_gap=None,
        ),
        model_dump=lambda **_kwargs: {
            "total": 2,
            "summary": {
                "cheapest_product_name": None,
                "lowest_current_price": None,
                "price_gap": None,
            },
        },
    )
    monkeypatch.setattr(
        "app.services.assistant_service.get_product_comparison_response",
        lambda *_args, **_kwargs: comparison,
    )

    answer, grounded_data = AssistantService()._build_answer(
        None,
        user_id=1,
        intent="comparison",
        message="compare Phone One and Phone Two",
        products=products,
        entities={},
    )

    assert "none has a currently available marketplace offer" in answer
    assert "None" not in answer
    assert grounded_data["summary"]["lowest_current_price"] is None


def test_assistant_parses_lakh_price_alert() -> None:
    entities = extract_assistant_entities(
        "1 lakh ke andar mobile recommend karo"
    )

    assert entities["budget_max"] == "100000"


def test_price_alert_parser_does_not_use_product_model_number() -> None:
    assert _extract_target_price(
        "alert me at 100k for iphone 15"
    ) == 100000
    assert _extract_target_price(
        "alert me for iphone 15 at 100k"
    ) == 100000
    assert _extract_target_price("alert me at PKR 500") == 500
    assert _extract_target_price("1") is None


def test_price_alert_target_survives_numbered_product_clarification() -> None:
    entities = inherit_pending_entities(
        {"selection_indices": [1]},
        {
            "pending_intent": "set_price_alert",
            "pending_entities": {"target_price": "100000"},
        },
    )

    assert entities == {
        "target_price": "100000",
        "selection_indices": [1],
    }


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


def test_konsa_in_direct_specification_question_is_not_recommendation() -> None:
    message = "Apple iPhone 18 Pro Max is main processor konsa hai"

    assert detect_assistant_intent(message) == "product_details"
    assert extract_assistant_entities(message)["requested_fields"] == [
        "processor"
    ]


def test_unknown_named_product_does_not_reuse_stale_context() -> None:
    stale_product = SimpleNamespace(id=77, name="Apple iPhone 15")

    class Repository:
        @staticmethod
        def find_product_entities(*_args, **_kwargs):
            return []

        @staticmethod
        def get_products_by_ids(*_args, **_kwargs):
            return [stale_product]

    service = AssistantService(repository=Repository())
    resolved = service._resolve_products(
        None,
        message="Apple iPhone 18 Pro Max ka processor konsa hai",
        intent="product_details",
        entities={"brand": "Apple", "requested_fields": ["processor"]},
        context={"product_ids": [77], "selected_product_id": 77},
        explicit_products=[],
    )

    assert resolved == []


def test_missing_requested_specification_is_reported_without_guessing(
    monkeypatch,
) -> None:
    product = SimpleNamespace(
        id=1,
        name="Example Phone",
        model="Example",
        specifications={"Color": "Black"},
        variants=[],
    )
    monkeypatch.setattr(
        "app.services.assistant_service.get_product_listings_response",
        lambda *_args, **_kwargs: SimpleNamespace(items=[]),
    )

    answer, grounded_data = AssistantService()._build_answer(
        None,
        user_id=1,
        intent="product_details",
        message="Example Phone ka processor konsa hai",
        products=[product],
        entities={"requested_fields": ["processor"]},
    )

    assert "processor information VEXTRO catalog mein nahi mili" in answer
    assert "andaza laga kar ghalat jawab nahi dunga" in answer
    assert grounded_data["missing_requested_fields"] == ["processor"]


def test_generic_specification_words_are_not_product_name_terms() -> None:
    assert {"ram", "storage", "specs", "mobile", "phone"} <= STOP_WORDS


def test_product_candidate_query_uses_bounded_distinctive_terms() -> None:
    assert product_search_terms(
        "Compare Samsung Galaxy A55 with iPhone 15 Pro"
    ) == ["a55", "15"]
    assert len(product_search_terms(" ".join(f"term{x}" for x in range(20)))) == 8


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


def test_gemini_result_accepts_out_of_scope_intent() -> None:
    result = AssistantNLUResult(intent="out_of_scope")

    assert result.intent == "out_of_scope"
    assert result.extracted_entities() == {}


def test_gemini_result_maps_comparison_selection_indices() -> None:
    result = AssistantNLUResult(
        intent="comparison",
        selection_indices=[1, 2, 1],
    )

    assert result.extracted_entities() == {
        "selection_indices": [1, 2],
    }


def test_gemini_scope_verdict_overrides_shopping_keyword_intent() -> None:
    assert reconcile_assistant_intent(
        "lowest_price",
        "out_of_scope",
    ) == "out_of_scope"


def test_catalog_scope_gate_rejects_keyword_only_unrelated_questions() -> None:
    assert is_grounded_catalog_request(
        "lowest_price",
        local_entities={},
        context={},
        explicit_product_count=0,
    ) is False
    assert is_grounded_catalog_request(
        "price_history",
        local_entities={"brand": "Samsung"},
        context={},
        explicit_product_count=0,
    ) is False


def test_catalog_scope_gate_allows_exact_product_and_context_follow_up() -> None:
    assert is_grounded_catalog_request(
        "lowest_price",
        local_entities={},
        context={},
        explicit_product_count=1,
    ) is True
    assert is_grounded_catalog_request(
        "product_details",
        local_entities={"requested_fields": ["ram"]},
        context={"selected_product_id": 42},
        explicit_product_count=0,
    ) is True


def test_data_timestamp_comes_from_latest_source_observation() -> None:
    timestamp = latest_grounding_timestamp(
        {
            "items": [
                {"last_seen_at": "2026-01-01T10:00:00+00:00"},
                {"captured_at": "2026-01-03T09:00:00+00:00"},
            ],
            "generated_at": "2030-01-01T00:00:00+00:00",
        }
    )

    assert timestamp is not None
    assert timestamp.isoformat() == "2026-01-03T09:00:00+00:00"
    assert latest_grounding_timestamp({"generated_at": "2030-01-01"}) is None


def test_message_turn_conversation_query_supports_row_locking() -> None:
    class CapturingSession:
        statement = None

        def scalar(self, statement):
            self.statement = statement
            return None

    session = CapturingSession()
    AssistantRepository.get_conversation(
        session,
        conversation_id=1,
        user_id=2,
        for_update=True,
    )

    assert session.statement is not None
    assert session.statement._for_update_arg is not None


def test_gemini_can_recognize_an_ambiguous_catalog_request() -> None:
    assert reconcile_assistant_intent(
        "out_of_scope",
        "product_search",
    ) == "product_search"


def test_gemini_comparison_follow_up_wins_inside_comparison_context() -> None:
    assert reconcile_assistant_intent(
        "lowest_price",
        "comparison",
        {"comparison_product_ids": [1, 2]},
    ) == "comparison"


def test_gemini_buy_or_wait_wins_over_generic_price_keyword() -> None:
    assert reconcile_assistant_intent(
        "lowest_price",
        "buy_or_wait",
    ) == "buy_or_wait"


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


def test_same_budget_purchase_follow_up_drops_stale_camera_preference() -> None:
    entities = {"category": "Mobile Phones"}
    context = {
        "last_intent": "recommendation",
        "budget_max": "100000",
        "category": "Mobile Phones",
        "preference": "camera",
    }

    assert inherit_recommendation_context(
        entities,
        context,
        "muje konsa mobile purchase krna chahiye is budget main",
    ) == {
        "category": "Mobile Phones",
        "budget_max": "100000",
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


def test_processor_evidence_prefers_structured_catalog_specification() -> None:
    assert extract_processor_evidence(
        {"Processor": "Snapdragon 7s Gen 2", "Color": "Black"},
        "Phone with Helio G99",
    ) == "Snapdragon 7s Gen 2"


def test_processor_evidence_can_use_a_catalog_listing_title() -> None:
    assert extract_processor_evidence({}, "Phone - MediaTek Dimensity 7300") == (
        "Dimensity 7300"
    )
