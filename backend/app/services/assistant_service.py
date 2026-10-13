"""Grounded, deterministic conversational shopping assistant."""

import re
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.repositories.assistant_repository import (
    AssistantRepository,
    extract_camera_evidence,
)
from app.schemas.assistant import (
    AssistantMessageCreate,
    AssistantMessageResponse,
    AssistantTurnResponse,
    ConversationCreate,
    ConversationDetailResponse,
    ConversationListResponse,
    ConversationResponse,
)
from app.schemas.price_intelligence import PriceAlertCreate
from app.services.price_alert_service import (
    PriceAlertAlreadyExistsError,
    create_user_price_alert,
)
from app.services.price_intelligence_service import (
    get_personalized_buy_time_guidance_response,
    get_product_price_history_response,
)
from app.services.product_catalog_service import (
    get_product_listings_response,
)
from app.services.product_comparison_service import (
    get_product_comparison_response,
)
from app.services.assistant_nlu_service import GeminiAssistantNLUService


INTENT_PATTERNS = (
    ("set_price_alert", r"\b(alert|notify|notification|yaad dilana)\b|bata dena"),
    (
        "comparison",
        r"\b(compare|comapre|comparison|versus|vs|difference|better)\b|"
        r"muqabla|farq",
    ),
    ("price_history", r"\b(history|historical|trend|ever)\b|pehle ki (price|qeemat)|price record"),
    (
        "buy_or_wait",
        r"buy now|should i buy|\bwait\b|best time|"
        r"\bbuy\b.*\b(?:or not|ya nahi|ya nhi)\b|"
        r"ab(?:hi)?\s+(?:le|kharid|khareed)|"
        r"\b(?:kharid|khareed|le|loon|lu)\w*\b.*\bya\s+n(?:ahi|hi)\b|"
        r"\b(?:lena|loon|lu|kharidna|khareedna|kharidon)\s+chahiye\b|"
        r"intezar",
    ),
    (
        "recommendation",
        r"\b(recommend|suggest|similar|alternative|best(?:\s+option)?)\b|"
        r"kons[ai]|kaunsa|kaunsi|"
        r"which (phone|mobile|laptop|product).*(buy|choose)|"
        r"\b(phone|mobile|laptop|tablet)s?\b.*"
        r"\b(under|below|within|budget|andar|ander|andr|chahiye|chaiye)\b|"
        r"\bbudget\b.*\b(phone|mobile|laptop|tablet)s?\b",
    ),
    ("product_details", r"\b(spec|specification|ram|storage|battery|camera|processor|feature)s?\b|details?|kitni ram"),
    ("lowest_price", r"\b(lowest|cheapest|current price|price|cost|rate)\b|qeemat|kitne ka|kitni ki"),
    (
        "greeting",
        r"^(?:(?:hi|hello|hey|salam|assalam)(?:\s+(?:there|ji))?|help)[.!?]*$",
    ),
    ("acknowledgement", r"^(ok|okay|acha|achha|theek|thanks|thank you)(\s+(tell|batao|ji))?[.!?]*$"),
)

CATEGORY_TERMS = {
    "phone": "Mobile Phones",
    "phones": "Mobile Phones",
    "mobile": "Mobile Phones",
    "mobiles": "Mobile Phones",
    "smartphone": "Mobile Phones",
    "smart phone": "Mobile Phones",
    "laptop": "Laptops",
    "laptops": "Laptops",
    "tablet": "Tablets",
    "tablets": "Tablets",
    "watch": "Smart Watches",
    "smartwatch": "Smart Watches",
    "earbud": "Audio and Earbuds",
    "earbuds": "Audio and Earbuds",
    "headphones": "Audio and Earbuds",
    "power bank": "Power Banks",
    "powerbank": "Power Banks",
    "accessory": "Mobile Accessories",
    "accessories": "Mobile Accessories",
}

KNOWN_BRANDS = (
    "apple", "samsung", "xiaomi", "oppo", "vivo", "infinix",
    "tecno", "realme", "oneplus", "huawei", "honor", "nokia",
    "google", "motorola", "nothing", "sony", "zte", "itel", "qmobile",
    "vgotel", "lg", "sharp", "dcode", "balmuda", "sego", "villaon",
    "dell", "hp", "lenovo", "asus", "acer",
)


def detect_assistant_intent(message: str) -> str:
    """Classify one supported assistant intent without inventing data."""

    normalized = message.strip().lower()

    # A budget plus a product category is a recommendation request even when
    # users say "dikhao" instead of the literal "recommend". This covers
    # natural Roman-Urdu word order such as "60k ke andar mobile dikhao".
    extracted = extract_assistant_entities(message)
    if extracted.get("category") and (
        extracted.get("budget_min") or extracted.get("budget_max")
    ):
        return "recommendation"

    # A request for a concrete field is a specification lookup, even when the
    # user naturally says "konsa" (for example, "iPhone 18 ka processor konsa
    # hai").  Previously the broad recommendation keyword won first and an
    # unknown model produced unrelated catalog recommendations.
    hardware_fields = {
        "ram", "storage", "camera", "battery", "processor", "display"
    }
    if (
        hardware_fields.intersection(extracted.get("requested_fields", []))
        and not re.search(
            r"\b(recommend|suggest|best|better|behtar|acha|achi|compare|"
            r"comparison|versus|vs)\b|muqabla|farq",
            normalized,
        )
    ):
        return "product_details"

    # Treat use-case questions as recommendations, even when the user does not
    # use the literal word "recommend". This is especially important for
    # follow-ups such as "camera quality achi chahiye" after a budget request.
    if re.search(
        r"\b(camera|photography|photo|selfie)\b.*"
        r"\b(best|better|acha|achi|chahiye|quality)\b|"
        r"\b(best|better|acha|achi|chahiye|quality)\b.*"
        r"\b(camera|photography|photo|selfie)\b",
        normalized,
    ):
        return "recommendation"

    for intent, pattern in INTENT_PATTERNS:
        if re.search(pattern, normalized):
            return intent

    # Unknown text must fail closed instead of being treated as a catalog
    # search. Known catalog language still gets a deterministic fallback when
    # Gemini is disabled or temporarily unavailable.
    shopping_scope_terms = (
        *CATEGORY_TERMS.keys(),
        *KNOWN_BRANDS,
        "product",
        "products",
        "catalog",
        "marketplace",
        "listing",
        "offer",
        "deal",
    )
    if any(
        re.search(rf"\b{re.escape(term)}\b", normalized)
        for term in shopping_scope_terms
    ):
        return "product_search"

    return "out_of_scope"


def reconcile_assistant_intent(
    local_intent: str,
    ai_intent: str,
    context: dict[str, object] | None = None,
) -> str:
    """Combine deterministic parsing with Gemini's scope decision safely."""

    # Scope is Gemini's primary responsibility. A keyword such as "price" in
    # an unrelated question (for example, cryptocurrency) must never override
    # its out-of-scope verdict.
    if ai_intent == "out_of_scope":
        return "out_of_scope"

    # Natural buy/no-buy wording often also contains "price". Gemini's
    # explicit buy_or_wait interpretation is more specific than the local
    # lowest-price keyword in that case.
    if ai_intent == "buy_or_wait":
        return "buy_or_wait"

    if (
        ai_intent == "comparison"
        and (context or {}).get("comparison_product_ids")
    ):
        return "comparison"

    high_confidence_local_intents = {
        "set_price_alert",
        "comparison",
        "price_history",
        "buy_or_wait",
        "product_details",
        "lowest_price",
        "greeting",
        "acknowledgement",
    }
    if local_intent in high_confidence_local_intents:
        return local_intent
    return ai_intent


def is_named_product_comparison(
    message: str,
    product_count: int,
) -> bool:
    """Recognize a comparative question that explicitly names 2+ products."""

    if product_count < 2:
        return False
    normalized = message.lower()
    return bool(
        re.search(
            r"\b(compare|comparison|versus|vs|which|better|best|"
            r"behtar|acha|achi|stronger)\b|\bkon\s*sa\b|\bkaun\s*sa\b|"
            r"muqabla|farq|in\s+(?:dono|2)\s+(?:me|mein)",
            normalized,
        )
    )


def _parse_money_value(number: str, suffix: str | None) -> Decimal:
    value = Decimal(number.replace(",", ""))
    normalized_suffix = (suffix or "").lower()
    if normalized_suffix in {"k", "thousand", "hazar", "hazaar"}:
        # Users often type a redundant suffix after a complete amount, for
        # example "100000 k budget". Treating that as 100 million makes the
        # budget filter silently disappear in practice.
        if value < 10000:
            value *= 1000
    elif normalized_suffix in {"lac", "lakh"}:
        value *= 100000
    return value


def _money_candidates(message: str) -> list[Decimal]:
    matches = re.findall(
        r"(?:pkr|rs\.?)?\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)\s*"
        r"(k|thousand|hazar|hazaar|lac|lakh)?\b",
        message.lower(),
    )
    return [_parse_money_value(number, suffix) for number, suffix in matches]


def extract_assistant_entities(message: str) -> dict[str, object]:
    """Extract budget, category, variant and reference entities."""

    normalized = message.lower()
    entities: dict[str, object] = {}

    if re.search(r"\b(camera|photography|photo|photos|selfie)\b", normalized):
        entities["preference"] = "camera"

    requested_fields = []
    requested_field_patterns = {
        "ram": r"\bram\b",
        "storage": r"\b(storage|rom|memory)\b",
        "camera": r"\b(camera|photography|photo|selfie)\b",
        "battery": r"\bbattery\b",
        "processor": r"\b(processor|chipset|cpu)\b",
        "display": r"\b(display|screen)\b",
        "price": r"\b(price|cost|rate|qeemat)\b",
        "rating": r"\b(rating|review score)\b",
    }
    for field, pattern in requested_field_patterns.items():
        if re.search(pattern, normalized):
            requested_fields.append(field)
    if requested_fields:
        entities["requested_fields"] = requested_fields

    numeric_selection = re.search(
        r"\b([1-4])(?:st|nd|rd|th)?\s*"
        r"(?:and|aur|or|&|,|\s+)\s*"
        r"([1-4])(?:st|nd|rd|th)?\b",
        normalized,
    )
    if numeric_selection and numeric_selection.group(1) != numeric_selection.group(2):
        entities["selection_indices"] = [
            int(numeric_selection.group(1)),
            int(numeric_selection.group(2)),
        ]
    elif re.search(
        r"\b(first|1st|pehla|pehle)\b.*"
        r"\b(second|2nd|dusra|doosra|dusre)\b|"
        r"\b(second|2nd|dusra|doosra|dusre)\b.*"
        r"\b(first|1st|pehla|pehle)\b",
        normalized,
    ):
        entities["selection_indices"] = [1, 2]
    else:
        single_selection = re.fullmatch(
            r"\s*([1-4])(?:st|nd|rd|th)?"
            r"(?:\s*(?:wala|wali|ko|please))?\s*[.!]?\s*",
            normalized,
        )
        if single_selection:
            entities["selection_indices"] = [int(single_selection.group(1))]
    amounts = [amount for amount in _money_candidates(normalized) if amount >= 1000]
    under_phrase = re.search(
        r"(under|below|within|up to|less than|se kam|"
        r"(?:k|ke)?\s*(?:andar|ander|andr))",
        normalized,
    )
    amount_before_limit = re.search(
        r"(?:pkr|rs\.?)?\s*"
        r"([0-9][0-9,]*(?:\.[0-9]{1,2})?)\s*"
        r"(k|thousand|hazar|hazaar|lac|lakh)?\s*"
        r"(?:k|ke)?\s*(?:andar|ander|andr|se kam)\b",
        normalized,
    )
    amount_after_limit = re.search(
        r"(?:under|below|within|up to|less than)\s*"
        r"(?:pkr|rs\.?)?\s*"
        r"([0-9][0-9,]*(?:\.[0-9]{1,2})?)\s*"
        r"(k|thousand|hazar|hazaar|lac|lakh)?\b",
        normalized,
    )
    between_phrase = re.search(r"(between|darmiyan|se).*(and|aur|to|tak)", normalized)

    if len(amounts) >= 2 and between_phrase:
        entities["budget_min"] = str(min(amounts[0], amounts[1]))
        entities["budget_max"] = str(max(amounts[0], amounts[1]))
    elif amount_before_limit or amount_after_limit:
        limit_match = amount_before_limit or amount_after_limit
        entities["budget_max"] = str(
            _parse_money_value(limit_match.group(1), limit_match.group(2))
        )
    elif amounts and under_phrase:
        entities["budget_max"] = str(amounts[0])
    elif amounts and re.search(
        r"\b(budget|range|around|approximately|approx|taqreeban|tak)\b",
        normalized,
    ):
        entities["budget_max"] = str(amounts[0])

    for term, category in CATEGORY_TERMS.items():
        if re.search(rf"\b{re.escape(term)}s?\b", normalized):
            entities["category"] = category
            break

    for brand in KNOWN_BRANDS:
        if re.search(rf"\b{re.escape(brand)}\b", normalized):
            entities["brand"] = brand.title()
            break

    ram_match = re.search(r"\b(\d{1,2})\s*gb\s*ram\b|\bram\s*(\d{1,2})\s*gb", normalized)
    if ram_match:
        entities["ram_gb"] = int(next(value for value in ram_match.groups() if value))
        if "ram" in entities.get("requested_fields", []):
            entities["requested_fields"].remove("ram")

    storage_match = re.search(
        r"\b(\d{2,4})\s*gb\s*(?:storage|rom)\b|\b(?:storage|rom)\s*(\d{2,4})\s*gb",
        normalized,
    )
    if storage_match:
        entities["storage_gb"] = int(
            next(value for value in storage_match.groups() if value)
        )
        if "storage" in entities.get("requested_fields", []):
            entities["requested_fields"].remove("storage")

    if not entities.get("requested_fields"):
        entities.pop("requested_fields", None)

    reference_patterns = (
        (
            "previous_two",
            r"\b(previous|last)\s+(?:two|2)\b|"
            r"\bpichl(?:e|i)\s+dono\b|\bpehlay\s+walay\s+dono\b",
        ),
        (
            "all",
            r"\b(sab|saray|saare|tamam)\b|"
            r"\ball\s+(?:of\s+them|those|these|products|phones|mobiles)\b",
        ),
        ("second", r"\b(second|2nd|dusra|doosra|dusre)\b"),
        ("first", r"\b(first|1st|pehla|pehle)\b"),
        (
            "current",
            r"\b(this|it|its|that|previous|last|pichla|pichle|"
            r"is ka|iski|iska|iss|uska|yeh|ye)\b",
        ),
    )
    if "selection_indices" not in entities:
        for reference, pattern in reference_patterns:
            if re.search(pattern, normalized):
                entities["reference"] = reference
                break

    return entities


def inherit_recommendation_context(
    entities: dict[str, object],
    context: dict[str, object],
    message: str | None = None,
) -> dict[str, object]:
    """Carry filters only from the immediately relevant recommendation turn."""

    if context.get("last_intent") != "recommendation":
        return entities

    merged = dict(entities)
    has_new_budget = "budget_min" in entities or "budget_max" in entities
    budget_only_reference = bool(
        message
        and re.search(
            r"\b(?:is|iss|this)\s+budget\b|\bbudget\s+(?:main|mein)\b",
            message.lower(),
        )
        and not any(
            key in entities
            for key in ("brand", "ram_gb", "storage_gb", "preference")
        )
        and not entities.get("requested_fields")
    )
    keys = (
        ("budget_min", "budget_max", "category")
        if budget_only_reference
        else ("category",)
        if has_new_budget
        else (
            "budget_min", "budget_max", "category", "brand",
            "ram_gb", "storage_gb", "preference",
        )
    )
    for key in keys:
        if key not in merged and key in context:
            merged[key] = context[key]
    return merged


def _extract_target_price(message: str) -> Decimal | None:
    """Extract an explicitly priced alert target, not a product model number."""

    normalized = message.lower()
    money_pattern = re.compile(
        r"(?P<currency>pkr|rs\.?)?\s*"
        r"(?P<number>[0-9][0-9,]*(?:\.[0-9]{1,2})?)\s*"
        r"(?P<suffix>k|thousand|hazar|hazaar|lac|lakh)?\b",
    )
    ranked: list[tuple[int, int, Decimal]] = []
    for match in money_pattern.finditer(normalized):
        value = _parse_money_value(
            match.group("number"),
            match.group("suffix"),
        )
        if value <= 0:
            continue

        before = normalized[max(0, match.start() - 28):match.start()]
        after = normalized[match.end():match.end() + 18]
        score = 0
        if match.group("currency"):
            score += 5
        if match.group("suffix"):
            score += 4
        if re.search(
            r"(?:at|below|under|reaches?|drops?\s+to|target|price|"
            r"qeemat|tak|par)\s*$",
            before,
        ):
            score += 4
        if re.match(r"\s*(?:pkr|rs\.?|price|qeemat)\b", after):
            score += 3
        if value >= 1000:
            score += 2
        if re.search(
            r"(?:iphone|galaxy|pixel|note|redmi|vivo|oppo|infinix|"
            r"tecno|realme|oneplus|itel|model)\s*$",
            before,
        ):
            score -= 6

        # A bare one-digit selection ("1") is never an alert amount. Smaller
        # prices remain valid when the user marks them as PKR/Rs or uses a
        # target phrase such as "at 500".
        if score > 0 and not (value < 10 and score <= 2):
            ranked.append((score, match.start(), value))

    if not ranked:
        return None
    return max(ranked, key=lambda candidate: (candidate[0], -candidate[1]))[2]


def inherit_pending_entities(
    entities: dict[str, object],
    context: dict[str, object],
) -> dict[str, object]:
    """Restore validated entities saved before a numbered clarification."""

    pending = context.get("pending_entities")
    if not isinstance(pending, dict):
        return entities
    return {**pending, **entities}


def is_grounded_catalog_request(
    intent: str,
    *,
    local_entities: dict[str, object],
    context: dict[str, object],
    explicit_product_count: int,
) -> bool:
    """Fail closed unless a non-meta intent has catalog or turn evidence."""

    if intent in {"greeting", "acknowledgement", "out_of_scope"}:
        return True
    if explicit_product_count > 0:
        return True
    if local_entities.get("selection_indices") and context.get(
        "pending_product_ids",
    ):
        return True

    has_product_context = bool(
        context.get("selected_product_id")
        or context.get("pending_product_ids")
        or context.get("comparison_product_ids")
        or context.get("product_ids")
    )
    if has_product_context and (
        local_entities.get("reference")
        or intent in {
            "product_details",
            "lowest_price",
            "price_history",
            "buy_or_wait",
            "set_price_alert",
            "comparison",
        }
    ):
        return True

    if intent == "recommendation":
        return bool(
            local_entities.get("category")
            or local_entities.get("brand")
            or local_entities.get("budget_min")
            or local_entities.get("budget_max")
            or context.get("last_intent") == "recommendation"
        )
    if intent == "product_search":
        return bool(
            local_entities.get("category")
            or local_entities.get("brand")
        )
    if intent == "lowest_price" and local_entities.get("category"):
        return True
    return False


def latest_grounding_timestamp(
    grounded_data: dict[str, object],
) -> datetime | None:
    """Return the newest real source-observation timestamp in grounded data."""

    timestamp_keys = {"last_seen_at", "captured_at", "last_captured_at"}
    candidates: list[datetime] = []

    def visit(value: object, key: str | None = None) -> None:
        if key in timestamp_keys:
            parsed = value
            if isinstance(parsed, str):
                try:
                    parsed = datetime.fromisoformat(
                        parsed.replace("Z", "+00:00")
                    )
                except ValueError:
                    parsed = None
            if isinstance(parsed, datetime):
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                candidates.append(parsed)
        if isinstance(value, dict):
            for child_key, child_value in value.items():
                visit(child_value, str(child_key))
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(grounded_data)
    return max(candidates) if candidates else None


class AssistantService:
    """Store conversations and answer only from VEXTRO data."""

    def __init__(
        self,
        repository: AssistantRepository | None = None,
        nlu_service: GeminiAssistantNLUService | None = None,
    ) -> None:
        self.repository = repository or AssistantRepository()
        self.nlu_service = nlu_service or GeminiAssistantNLUService()

    def create_conversation(
        self,
        database_session: Session,
        *,
        user_id: int,
        payload: ConversationCreate,
    ) -> ConversationResponse:
        conversation = self.repository.create_conversation(
            database_session,
            user_id=user_id,
            title=payload.title or "New shopping conversation",
        )
        database_session.commit()
        database_session.refresh(conversation)
        return ConversationResponse.model_validate(conversation)

    def list_conversations(
        self,
        database_session: Session,
        *,
        user_id: int,
        page: int = 1,
        page_size: int = 50,
    ) -> ConversationListResponse:
        total, conversations = self.repository.list_conversations(
            database_session,
            user_id=user_id,
            offset=(page - 1) * page_size,
            limit=page_size,
        )
        return ConversationListResponse(
            total=total,
            items=[
                ConversationResponse.model_validate(conversation)
                for conversation in conversations
            ],
            page=page,
            page_size=page_size,
        )

    def get_conversation(
        self,
        database_session: Session,
        *,
        conversation_id: int,
        user_id: int,
        message_limit: int = 100,
        before_message_id: int | None = None,
    ) -> ConversationDetailResponse:
        conversation = self.repository.get_conversation(
            database_session,
            conversation_id=conversation_id,
            user_id=user_id,
        )

        if conversation is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="The requested conversation was not found.",
            )

        messages = self.repository.list_messages(
            database_session,
            conversation_id=conversation.id,
            limit=message_limit,
            before_message_id=before_message_id,
        )
        older_than = messages[0].id if messages else before_message_id
        has_more_messages = bool(
            older_than
            and self.repository.count_messages(
                database_session,
                conversation_id=conversation.id,
                before_message_id=older_than,
            )
        )
        total = self.repository.count_messages(
            database_session,
            conversation_id=conversation.id,
        )
        base = ConversationResponse.model_validate(conversation)
        return ConversationDetailResponse(
            **base.model_dump(),
            messages=[
                AssistantMessageResponse.model_validate(message)
                for message in messages
            ],
            message_total=total,
            has_more_messages=has_more_messages,
        )

    def _resolve_products(
        self,
        database_session: Session,
        *,
        message: str,
        intent: str,
        entities: dict[str, object],
        context: dict[str, object],
        explicit_products=None,
    ):
        if explicit_products is None:
            explicit_products = self.repository.find_product_entities(
                database_session,
                message,
            )
        if intent == "recommendation" and entities.get("category"):
            normalized_message = message.lower()
            budget_number_tokens = set(
                re.findall(
                    r"\b([0-9][0-9,]*(?:\.[0-9]{1,2})?)\s*"
                    r"(?:k|thousand|lac|lakh)\b",
                    normalized_message,
                )
            )
            explicitly_modeled = []
            for product in explicit_products:
                model_terms = re.findall(
                    r"[a-z0-9]+", (product.model or "").lower()
                )
                generic_model_terms = {
                    "phone", "mobile", "smartphone", "laptop", "tablet",
                    "watch", "pro", "max", "plus", "5g", "4g",
                    "camera", "quality", "display", "battery", "ram",
                    "rom", "storage", "dual", "sim", "inches",
                }
                if (
                    product.name.lower() in normalized_message
                    or any(
                        len(term) >= 2
                        and term not in generic_model_terms
                        and term not in budget_number_tokens
                        and re.search(
                            rf"\b{re.escape(term)}\b", normalized_message
                        )
                        for term in model_terms
                    )
                ):
                    explicitly_modeled.append(product)
            explicit_products = explicitly_modeled
        selection_indices = entities.get("selection_indices", [])
        if (
            isinstance(selection_indices, list)
            and selection_indices
            and context.get("pending_product_ids")
        ):
            context_product_ids = context.get("pending_product_ids", [])
        elif intent == "comparison" and context.get("comparison_product_ids"):
            context_product_ids = context.get("comparison_product_ids", [])
        else:
            context_product_ids = context.get("product_ids", [])
        context_ids = [
            int(product_id)
            for product_id in context_product_ids
            if str(product_id).isdigit()
        ]
        contextual_products = self.repository.get_products_by_ids(
            database_session, context_ids
        )

        # A brand explicitly typed in the current turn means the user is
        # naming a new product. If it did not match the catalog, never answer
        # with a stale product remembered from an earlier turn.
        mentions_brand = any(
            re.search(rf"\b{re.escape(brand)}\b", message.lower())
            for brand in KNOWN_BRANDS
        )
        if (
            not explicit_products
            and mentions_brand
            and intent in {
                "product_details",
                "lowest_price",
                "price_history",
                "buy_or_wait",
                "set_price_alert",
            }
        ):
            return []

        # A filtered recommendation follow-up (for example, adding a camera
        # preference to the previous 80k request) must re-rank the whole
        # eligible catalog. Previous recommendation cards are context, not
        # products to exclude from the new result set.
        if (
            intent == "recommendation"
            and entities.get("category")
            and not explicit_products
        ):
            return []

        # A product named in the current message always replaces stale
        # conversational selection. Previously, asking for "iPhone 17 Pro"
        # after discussing Samsung A57 returned the Samsung price because the
        # remembered selected_product_id was checked first.
        if explicit_products and intent != "comparison":
            return explicit_products

        if (
            not explicit_products
            and isinstance(selection_indices, list)
            and selection_indices
            and contextual_products
        ):
            selected = []
            for one_based_index in selection_indices:
                if not isinstance(one_based_index, int):
                    continue
                zero_based_index = one_based_index - 1
                if 0 <= zero_based_index < len(contextual_products):
                    product = contextual_products[zero_based_index]
                    if product not in selected:
                        selected.append(product)
            if selected:
                return selected

        reference = entities.get("reference")
        if intent != "comparison" and contextual_products:
            if reference == "second" and len(contextual_products) >= 2:
                return [contextual_products[1]]
            if reference in {"first", "current"}:
                return [contextual_products[0]]
            selected_product_id = context.get("selected_product_id")
            if selected_product_id is not None:
                selected = next(
                    (
                        product for product in contextual_products
                        if product.id == selected_product_id
                    ),
                    None,
                )
                if selected is not None:
                    return [selected]

        if intent == "comparison" and explicit_products:
            # When the user names two or more products, those names are the
            # complete comparison target. Pulling an older recommendation from
            # context produced surprising third rows in otherwise explicit
            # two-product comparisons.
            if len(explicit_products) >= 2:
                return explicit_products[:4]
            if not entities.get("reference"):
                return explicit_products
            combined = list(explicit_products)
            existing_ids = {product.id for product in combined}
            for product in contextual_products:
                if product.id not in existing_ids:
                    combined.append(product)
            return combined[:3]

        if (
            intent == "comparison"
            and reference == "previous_two"
            and len(contextual_products) >= 2
        ):
            return contextual_products[:2]

        return contextual_products

    def _build_answer(
        self,
        database_session: Session,
        *,
        user_id: int,
        intent: str,
        message: str,
        products,
        entities: dict[str, object],
    ) -> tuple[str, dict[str, object]]:
        if intent == "greeting":
            return (
                "Hello! I can find products, answer specification and price "
                "questions, compare models, show price history, recommend "
                "options within a budget, give buy/wait guidance, and create "
                "price alerts. Try: '80k ke andar phone recommend karo'.",
                {
                    "capabilities": [
                        "product_search",
                        "product_details",
                        "lowest_price",
                        "comparison",
                        "price_history",
                        "recommendation",
                        "buy_or_wait",
                        "set_price_alert",
                    ],
                },
            )

        if intent == "acknowledgement":
            return (
                "Ji. Aap product ki price, specifications, comparison, "
                "price history ya apne budget ke andar recommendation "
                "pooch sakte hain.",
                {
                    "matched_products": [],
                },
            )

        if intent == "out_of_scope":
            return (
                "Sorry, I can't help with that request. I can only help with "
                "VEXTRO products, current prices, specifications, comparisons, "
                "stored price history, budget recommendations, buy/wait guidance, "
                "and price alerts. Try asking: '80k ke andar best phone recommend "
                "karo'.",
                {
                    "matched_products": [],
                    "scope": "out_of_scope",
                    "capabilities": [
                        "product_search",
                        "product_details",
                        "lowest_price",
                        "comparison",
                        "price_history",
                        "recommendation",
                        "buy_or_wait",
                        "set_price_alert",
                    ],
                },
            )

        if intent == "recommendation":
            seed = products[0] if products else None
            category = entities.get("category")
            if category is None and seed is not None:
                # Category IDs are reliable for ranking even if a category name
                # was not explicitly included in the message.
                similar = self.repository.find_similar_products(
                    database_session, seed
                )
                recommendations = []
                for item in similar:
                    offers = get_product_listings_response(database_session, item.id)
                    if offers and offers.items:
                        lowest_offer = offers.items[0]
                        budget_max = (
                            Decimal(str(entities["budget_max"]))
                            if entities.get("budget_max") else None
                        )
                        if (
                            budget_max is not None
                            and lowest_offer.current_price > budget_max
                        ):
                            continue
                        recommendations.append(
                            {
                                "id": item.id,
                                "name": item.name,
                                "model": item.model,
                                "lowest_price": str(lowest_offer.current_price),
                                "last_seen_at": (
                                    lowest_offer.last_seen_at.isoformat()
                                ),
                                "rating": (
                                    str(lowest_offer.rating)
                                    if lowest_offer.rating is not None else None
                                ),
                            }
                        )
            else:
                recommendations = self.repository.recommend_products(
                    database_session,
                    category=str(category) if category else None,
                    brand=(
                        str(entities["brand"])
                        if entities.get("brand") else None
                    ),
                    budget_min=(
                        Decimal(str(entities["budget_min"]))
                        if entities.get("budget_min") else None
                    ),
                    budget_max=(
                        Decimal(str(entities["budget_max"]))
                        if entities.get("budget_max") else None
                    ),
                    ram_gb=(
                        int(entities["ram_gb"])
                        if entities.get("ram_gb") else None
                    ),
                    storage_gb=(
                        int(entities["storage_gb"])
                        if entities.get("storage_gb") else None
                    ),
                    preference=(
                        str(entities["preference"])
                        if entities.get("preference") else None
                    ),
                    requested_fields=[
                        str(field)
                        for field in entities.get("requested_fields", [])
                    ],
                    exclude_ids=[product.id for product in products],
                )

            if not recommendations:
                budget_text = (
                    f" within PKR {entities['budget_max']}"
                    if entities.get("budget_max") else ""
                )
                return (
                    f"I could not find an available catalog option{budget_text}. "
                    "Try a different budget, category, or brand.",
                    {
                        "matched_products": [],
                        "recommendations": [],
                        "filters": entities,
                    },
                )

            requested_fields = set(entities.get("requested_fields", []))
            if (
                entities.get("preference") == "camera"
                and "processor" in requested_fields
            ):
                names = [
                    f"{item['name']} (PKR {item['lowest_price']}; "
                    f"{item['preference_evidence']}; listed processor: "
                    f"{item['processor_evidence']})"
                    for item in recommendations[:4]
                ]
                return (
                    "For your camera and processor requirements, the catalog "
                    "options with evidence for both are: "
                    + "; ".join(names)
                    + ". Camera ranking uses listed megapixels; processor "
                    "names are shown as catalog evidence because normalized "
                    "performance benchmarks are not stored.",
                    {
                        "matched_products": [
                            {"id": product.id, "name": product.name}
                            for product in products
                        ],
                        "recommendations": recommendations,
                        "filters": entities,
                        "method": (
                            "camera evidence, processor presence, rating, "
                            "and budget fit"
                        ),
                    },
                )

            if entities.get("preference") == "camera":
                names = [
                    f"{item['name']} (PKR {item['lowest_price']}; "
                    f"{item['preference_evidence']})"
                    for item in recommendations[:4]
                ]
                return (
                    "For camera priority, my strongest catalog-backed picks are: "
                    + "; ".join(names)
                    + ". I ranked only products that have camera details in the "
                    "catalog. Note: megapixels alone do not guarantee photo "
                    "quality; sensor size, OIS and image processing data are not "
                    "available in these listings.",
                    {
                        "matched_products": [
                            {"id": product.id, "name": product.name}
                            for product in products
                        ],
                        "recommendations": recommendations,
                        "filters": entities,
                        "method": "catalog camera evidence, rating, and budget fit",
                    },
                )

            names = [
                f"{item['name']} (PKR {item['lowest_price']})"
                for item in recommendations[:4]
            ]
            reason = (
                "live offers ranked by closest budget fit, then rating"
                if entities.get("budget_max")
                else "live offers ranked by rating and catalog price"
            )
            return (
                "My catalog picks are: " + "; ".join(names) + f". I used {reason}.",
                {
                    "matched_products": [
                        {"id": product.id, "name": product.name}
                        for product in products
                    ],
                    "recommendations": recommendations,
                    "filters": entities,
                    "method": "catalog price-and-rating ranking",
                },
            )

        if not products:
            requested_fields = [
                str(field) for field in entities.get("requested_fields", [])
            ]
            if intent == "product_details" and requested_fields:
                requested_text = ", ".join(requested_fields)
                return (
                    "Mujhe is product ki verified "
                    f"{requested_text} information VEXTRO catalog mein nahi "
                    "mili. Main andaza laga kar ghalat jawab nahi dunga.",
                    {
                        "matched_products": [],
                        "requested_fields": requested_fields,
                        "data_status": "requested specification unavailable",
                    },
                )
            return (
                "I could not match that request to an active VEXTRO "
                "catalog product. Please include a brand and model, for "
                "example 'Samsung Galaxy A55'.",
                {"matched_products": []},
            )

        matched = [
            {
                "id": product.id,
                "name": product.name,
                "model": product.model,
            }
            for product in products
        ]

        if intent == "comparison":
            if len(products) < 2:
                return (
                    "I found only one product. Please name a second "
                    "product so I can compare verified catalog records.",
                    {"matched_products": matched},
                )

            if len(products) > 3:
                choices = ", ".join(
                    f"{index + 1}) {product.name}"
                    for index, product in enumerate(products[:4])
                )
                return (
                    "Please choose two products to compare: " + choices + ".",
                    {
                        "matched_products": matched,
                        "needs_clarification": True,
                    },
                )

            comparison = get_product_comparison_response(
                database_session,
                [product.id for product in products[:3]],
            )
            assert comparison is not None
            requested_fields = set(entities.get("requested_fields", []))
            if (
                entities.get("preference") == "camera"
                or "camera" in requested_fields
            ):
                camera_rows = []
                for item in comparison.items:
                    evidence = extract_camera_evidence(
                        item.product.specifications or {},
                        " || ".join(
                            listing.title for listing in item.listings.items
                        ),
                    )
                    camera_rows.append(
                        {
                            "product_id": item.product.id,
                            "product_name": item.product.name,
                            "rear_mp": evidence[0] if evidence else None,
                            "front_mp": evidence[1] if evidence else None,
                            "evidence": evidence[2] if evidence else None,
                        }
                    )

                comparison_data = comparison.model_dump(mode="json")
                comparison_data["camera_comparison"] = camera_rows
                available = [
                    row for row in camera_rows
                    if row["rear_mp"] is not None
                ]
                evidence_text = "; ".join(
                    f"{row['product_name']}: "
                    + (row["evidence"] or "camera details unavailable")
                    for row in camera_rows
                )
                if len(available) != len(camera_rows):
                    return (
                        "I cannot reliably decide which has the better camera "
                        "because complete camera specifications are not stored "
                        f"for both products. Catalog evidence: {evidence_text}. "
                        "I will not guess from brand or price.",
                        comparison_data,
                    )

                best_score = max(
                    (row["rear_mp"], row["front_mp"] or 0)
                    for row in available
                )
                leaders = [
                    row for row in available
                    if (row["rear_mp"], row["front_mp"] or 0) == best_score
                ]
                if len(leaders) == 1:
                    verdict = (
                        f"{leaders[0]['product_name']} has the stronger "
                        "catalog-listed megapixel specification"
                    )
                else:
                    verdict = (
                        "The catalog-listed megapixel specifications are tied "
                        "for "
                        + " and ".join(row["product_name"] for row in leaders)
                    )
                return (
                    f"{verdict}. {evidence_text}. This does not prove actual "
                    "photo quality: sensor size, OIS, lens quality and image "
                    "processing benchmark data are not available, so I will "
                    "not claim an overall camera-quality winner.",
                    comparison_data,
                )

            summary = comparison.summary
            comparison_data = comparison.model_dump(mode="json")
            if (
                summary.cheapest_product_name is None
                or summary.lowest_current_price is None
            ):
                return (
                    f"Compared {comparison.total} products, but none has a "
                    "currently available marketplace offer in VEXTRO. I can "
                    "compare their stored specifications, but I cannot make "
                    "a current price comparison yet.",
                    comparison_data,
                )

            if summary.price_gap is None:
                return (
                    f"Compared {comparison.total} products. Only "
                    f"{summary.cheapest_product_name} has a currently "
                    f"available offer, at PKR {summary.lowest_current_price}. "
                    "A price gap cannot be calculated until another compared "
                    "product has an available offer.",
                    comparison_data,
                )

            content = (
                f"Compared {comparison.total} products. "
                f"{summary.cheapest_product_name} currently has the "
                f"lowest offer at PKR {summary.lowest_current_price}. "
                f"The observed price gap is PKR {summary.price_gap}."
            )
            return content, comparison_data

        single_product_intents = {
            "product_details",
            "lowest_price",
            "price_history",
            "buy_or_wait",
            "set_price_alert",
        }
        if intent in single_product_intents and len(products) > 1:
            choices = ", ".join(
                f"{index + 1}) {item.name}"
                for index, item in enumerate(products[:4])
            )
            return (
                "Which product do you mean? " + choices + ".",
                {
                    "matched_products": matched,
                    "needs_clarification": True,
                },
            )

        product = products[0]

        if intent == "price_history":
            history = get_product_price_history_response(
                database_session,
                product.id,
            )
            assert history is not None
            lows = [
                listing.summary.lowest_price
                for listing in history.listings
                if listing.summary.lowest_price is not None
            ]
            low_text = f"PKR {min(lows)}" if lows else "not available"
            return (
                f"{product.name} has {history.total_points} stored price "
                f"observations across {history.total_listings} listings. "
                f"The observed low is {low_text}.",
                history.model_dump(mode="json"),
            )

        if intent == "buy_or_wait":
            guidance = get_personalized_buy_time_guidance_response(
                database_session,
                product.id,
                user_id=user_id,
            )
            assert guidance is not None
            labels = {
                "buy_now": "Buy now",
                "wait": "Wait",
                "price_stable": "Price is stable",
                "insufficient_data": "Insufficient data",
            }
            personalization_text = (
                " Your saved price target is applied."
                if guidance.is_personalized
                else " Create a price alert to personalize this signal."
            )
            return (
                f"{labels[guidance.suggestion]} for {product.name}."
                f"{personalization_text} "
                f"Confidence is {guidance.confidence}; this uses "
                f"{guidance.observation_count} stored observations over "
                f"{guidance.coverage_days} day(s). "
                f"{guidance.reasons[0]}",
                guidance.model_dump(mode="json"),
            )

        if intent == "set_price_alert":
            target_value = entities.get("target_price")
            target_price = (
                Decimal(str(target_value))
                if target_value is not None
                else _extract_target_price(message)
            )

            if target_price is None:
                return (
                    f"Tell me the target price for {product.name}, for "
                    f"example 'alert me at PKR 110000'.",
                    {"matched_products": matched},
                )

            try:
                alert = create_user_price_alert(
                    database_session,
                    user_id=user_id,
                    payload=PriceAlertCreate(
                        canonical_product_id=product.id,
                        target_price=target_price,
                        currency="PKR",
                    ),
                )
            except PriceAlertAlreadyExistsError:
                return (
                    f"An active price alert already exists for "
                    f"{product.name}. You can update it from Price Alerts.",
                    {"matched_products": matched},
                )

            return (
                f"Price alert created for {product.name} at PKR "
                f"{alert.target_price}.",
                {
                    "matched_products": matched,
                    "price_alert": alert.model_dump(mode="json"),
                },
            )

        listings = get_product_listings_response(
            database_session,
            product.id,
        )
        assert listings is not None

        if intent == "lowest_price":
            if not listings.items:
                return (
                    f"{product.name} is in the catalog, but no available "
                    "marketplace offer is stored right now.",
                    {"matched_products": matched, "listings": []},
                )

            lowest = listings.items[0]
            return (
                f"The lowest stored offer for {product.name} is PKR "
                f"{lowest.current_price}. Data last observed at "
                f"{lowest.last_seen_at.isoformat()}.",
                {
                    "matched_products": matched,
                    "lowest_listing": lowest.model_dump(mode="json"),
                },
            )

        if intent == "product_details":
            if len(products) > 1:
                choices = ", ".join(
                    f"{index + 1}) {item.name}"
                    for index, item in enumerate(products[:4])
                )
                return (
                    "Which product do you mean? " + choices + ".",
                    {
                        "matched_products": matched,
                        "needs_clarification": True,
                    },
                )

            variants = []
            for variant in product.variants:
                variants.append(
                    {
                        "ram_gb": variant.ram_gb,
                        "storage_gb": variant.storage_gb,
                        "color": variant.color,
                        "condition": variant.condition,
                        "attributes": variant.variant_attributes,
                    }
                )
            if entities.get("preference") == "camera":
                camera_evidence = extract_camera_evidence(
                    product.specifications or {},
                    " || ".join(item.title for item in listings.items),
                )
                if camera_evidence is None:
                    return (
                        f"I found {product.name}, but its catalog records do "
                        "not contain camera specifications. I cannot judge its "
                        "camera quality from unrelated details such as color.",
                        {
                            "matched_products": matched,
                            "camera_evidence": None,
                            "data_status": "camera specifications unavailable",
                        },
                    )

                _, _, evidence_text = camera_evidence
                return (
                    f"{product.name}: {evidence_text}. This is seller-listed "
                    "specification data, not a camera-quality benchmark; sensor "
                    "size, OIS and image-processing evidence is unavailable.",
                    {
                        "matched_products": matched,
                        "camera_evidence": evidence_text,
                        "specifications": product.specifications or {},
                    },
                )

            requested_fields = set(entities.get("requested_fields", []))
            specification_priority = {
                "ram": 0,
                "memory": 1,
                "storage": 1,
                "rom": 1,
                "processor": 2,
                "chipset": 2,
                "cpu": 2,
                "camera": 3,
                "battery": 4,
                "display": 5,
                "screen": 5,
            }
            specification_items = sorted(
                (product.specifications or {}).items(),
                key=lambda item: min(
                    (
                        priority
                        for term, priority in specification_priority.items()
                        if term in str(item[0]).lower()
                    ),
                    default=50,
                ),
            )
            specification_parts = [
                f"{key}: {value}"
                for key, value in specification_items
                if value not in (None, "", [], {})
                and (
                    not requested_fields
                    or any(
                        field in str(key).lower()
                        for field in requested_fields
                    )
                )
            ][:6]
            variant_parts = []
            available_requested_fields = {
                field
                for field in requested_fields
                if any(
                    field in str(key).lower()
                    and value not in (None, "", [], {})
                    for key, value in (product.specifications or {}).items()
                )
            }
            for variant in variants[:4]:
                values = []
                if variant["ram_gb"] and (
                    not requested_fields or "ram" in requested_fields
                ):
                    values.append(f"{variant['ram_gb']}GB RAM")
                    available_requested_fields.add("ram")
                if variant["storage_gb"] and (
                    not requested_fields or "storage" in requested_fields
                ):
                    values.append(
                        f"{variant['storage_gb']}GB ROM/storage"
                    )
                    available_requested_fields.add("storage")
                if variant["color"] and not requested_fields:
                    values.append(str(variant["color"]))
                if values:
                    variant_parts.append(" / ".join(values))
            detail_text = "; ".join(specification_parts + variant_parts)
            missing_requested_fields = sorted(
                requested_fields - available_requested_fields
            )
            if not detail_text and missing_requested_fields:
                missing_text = ", ".join(missing_requested_fields)
                return (
                    f"Mujhe {product.name} ki verified {missing_text} "
                    "information VEXTRO catalog mein nahi mili. Main andaza "
                    "laga kar ghalat jawab nahi dunga.",
                    {
                        "matched_products": matched,
                        "specifications": product.specifications or {},
                        "variants": variants,
                        "missing_requested_fields": missing_requested_fields,
                        "data_status": "requested specification unavailable",
                    },
                )
            if not detail_text:
                detail_text = "No structured specifications are stored yet"
            missing_text = (
                " Catalog mein "
                + ", ".join(missing_requested_fields)
                + " information nahi mili."
                if missing_requested_fields
                else ""
            )
            return (
                f"{product.name}: {detail_text}.{missing_text}",
                {
                    "matched_products": matched,
                    "specifications": product.specifications or {},
                    "variants": variants,
                    "missing_requested_fields": missing_requested_fields,
                },
            )

        return (
            "I found "
            + ", ".join(product["name"] for product in matched)
            + ". Ask me for the lowest price, comparison, price history, "
            "buy/wait guidance, alternatives, or a price alert.",
            {"matched_products": matched},
        )

    def add_user_message(
        self,
        database_session: Session,
        *,
        conversation_id: int,
        user_id: int,
        payload: AssistantMessageCreate,
    ) -> AssistantTurnResponse:
        conversation = self.repository.get_conversation(
            database_session,
            conversation_id=conversation_id,
            user_id=user_id,
            for_update=True,
        )

        if conversation is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="The requested conversation was not found.",
            )

        local_intent = detect_assistant_intent(payload.content)
        intent = local_intent
        local_entities = extract_assistant_entities(payload.content)
        entities = dict(local_entities)
        if local_intent == "set_price_alert":
            target_price = _extract_target_price(payload.content)
            if target_price is not None:
                entities["target_price"] = str(target_price)

        explicit_products = self.repository.find_product_entities(
            database_session,
            payload.content,
        )

        remembered_products = self.repository.get_products_by_ids(
            database_session,
            [
                int(product_id)
                for product_id in conversation.context.get("product_ids", [])
                if str(product_id).isdigit()
            ],
        )
        remembered_comparison_products = self.repository.get_products_by_ids(
            database_session,
            [
                int(product_id)
                for product_id in conversation.context.get(
                    "comparison_product_ids",
                    [],
                )
                if str(product_id).isdigit()
            ],
        )
        ai_context = {
            **conversation.context,
            "product_names": [product.name for product in remembered_products],
            "comparison_product_names": [
                product.name for product in remembered_comparison_products
            ],
        }
        ai_analysis = self.nlu_service.analyze(
            payload.content,
            context=ai_context,
        )
        if ai_analysis is not None:
            # Explicit local phrases are deterministic and should not be
            # overridden by a model that inherited stale recommendation
            # context. Gemini decides only when the local parser is ambiguous.
            intent = reconcile_assistant_intent(
                local_intent,
                ai_analysis.intent,
                conversation.context,
            )
            ai_entities = ai_analysis.extracted_entities()
            # Exact locally parsed values (especially numeric budgets) win;
            # Gemini fills language/context gaps without becoming a fact source.
            requested_fields = list(dict.fromkeys([
                *ai_entities.pop("requested_fields", []),
                *entities.pop("requested_fields", []),
            ]))
            entities = {**ai_entities, **entities}
            if requested_fields:
                entities["requested_fields"] = requested_fields
        elif local_intent == "out_of_scope":
            # With Gemini unavailable, an exact database product match is
            # sufficient evidence that this is a catalog search. Everything
            # else remains out of scope instead of becoming a misleading
            # "not found in database" response.
            if (
                entities.get("selection_indices")
                and conversation.context.get("comparison_product_ids")
            ):
                intent = "comparison"
            else:
                if explicit_products:
                    intent = "product_search"

        selection_indices = entities.get("selection_indices", [])
        if isinstance(selection_indices, list) and selection_indices:
            pending_intent = conversation.context.get("pending_intent")
            if pending_intent is None:
                remembered_choice_ids = conversation.context.get(
                    "product_ids", []
                )
                if len(remembered_choice_ids) > 1:
                    pending_intent = conversation.context.get("last_intent")
            if pending_intent:
                intent = str(pending_intent)
                entities = inherit_pending_entities(
                    entities,
                    conversation.context,
                )

        # Two or more exact catalog names plus comparative wording is always a
        # comparison, even when "best camera" would otherwise look like a
        # broad recommendation. Product identity remains database-grounded.
        continues_existing_comparison = (
            bool(conversation.context.get("comparison_product_ids"))
            and entities.get("budget_min") is None
            and entities.get("budget_max") is None
            and entities.get("category") is None
            and is_named_product_comparison(payload.content, 2)
        )
        if (
            is_named_product_comparison(payload.content, len(explicit_products))
            or continues_existing_comparison
        ):
            intent = "comparison"
        if (
            intent == "out_of_scope"
            and local_intent != "out_of_scope"
            and explicit_products
        ):
            # An exact active-catalog match plus a deterministic shopping
            # intent is stronger evidence than a remote classifier refusal.
            intent = local_intent
        if not is_grounded_catalog_request(
            intent,
            local_entities=local_entities,
            context=conversation.context,
            explicit_product_count=len(explicit_products),
        ):
            intent = "out_of_scope"
        if (
            intent == "product_search"
            and conversation.context.get("last_intent") == "recommendation"
            and (
                entities.get("budget_max") is not None
                or re.search(
                    r"\b(i said|maine kaha|main ne kaha|tum ne|galat|wrong|budget)\b",
                    payload.content.lower(),
                )
            )
        ):
            intent = "recommendation"
        if intent == "recommendation":
            entities = inherit_recommendation_context(
                entities,
                conversation.context,
                payload.content,
            )
        if intent == "out_of_scope":
            # Do not query or attach catalog records to a rejected turn, even
            # when its text happens to contain a product or pricing keyword.
            entities = {}
            products = []
        else:
            products = self._resolve_products(
                database_session,
                message=payload.content,
                intent=intent,
                entities=entities,
                context=conversation.context,
                explicit_products=explicit_products,
            )
        entities.update(
            {
                "product_ids": [product.id for product in products],
                "product_names": [product.name for product in products],
            }
        )
        user_message = self.repository.add_message(
            database_session,
            conversation_id=conversation.id,
            role="user",
            content=payload.content,
            intent=intent,
            entities=entities,
        )

        try:
            answer, grounded_data = self._build_answer(
                database_session,
                user_id=user_id,
                intent=intent,
                message=payload.content,
                products=products,
                entities=entities,
            )
            data_timestamp = latest_grounding_timestamp(grounded_data)
            assistant_message = self.repository.add_message(
                database_session,
                conversation_id=conversation.id,
                role="assistant",
                content=answer,
                intent=intent,
                entities=entities,
                grounded_data=grounded_data,
                data_timestamp=data_timestamp,
            )
            recommendation_ids = [
                item.get("id")
                for item in grounded_data.get("recommendations", [])
                if isinstance(item, dict) and item.get("id") is not None
            ]
            remembered_ids = []
            for product_id in [
                *recommendation_ids,
                *entities["product_ids"],
                *conversation.context.get("product_ids", []),
            ]:
                if product_id not in remembered_ids:
                    remembered_ids.append(product_id)
            current_product_names = [
                item.get("name")
                for item in grounded_data.get("recommendations", [])[:4]
                if isinstance(item, dict) and item.get("name")
            ] or [product.name for product in products[:4]]
            context = {
                **conversation.context,
                "product_ids": remembered_ids[:4],
                "product_names": (
                    current_product_names
                    or conversation.context.get("product_names", [])
                ),
                "last_intent": (
                    conversation.context.get("last_intent")
                    if intent in {"acknowledgement", "out_of_scope"}
                    else intent
                ),
            }
            if (
                intent == "recommendation"
                and re.search(
                    r"\b(?:is|iss|this)\s+budget\b|"
                    r"\bbudget\s+(?:main|mein)\b",
                    payload.content.lower(),
                )
                and not entities.get("preference")
                and not entities.get("requested_fields")
            ):
                for stale_filter in (
                    "preference", "brand", "ram_gb", "storage_gb"
                ):
                    context.pop(stale_filter, None)
            if len(products) == 1 and intent in {
                "product_search",
                "product_details",
                "lowest_price",
                "price_history",
                "buy_or_wait",
                "set_price_alert",
            }:
                context["selected_product_id"] = products[0].id
            elif intent in {"recommendation", "comparison", "product_search"}:
                context.pop("selected_product_id", None)
            if intent == "comparison" and len(products) >= 2:
                context["comparison_product_ids"] = [
                    product.id for product in products[:4]
                ]
                context["comparison_product_names"] = [
                    product.name for product in products[:4]
                ]
            elif intent not in {"greeting", "acknowledgement", "out_of_scope"}:
                context.pop("comparison_product_ids", None)
                context.pop("comparison_product_names", None)
            if grounded_data.get("needs_clarification"):
                context["pending_intent"] = intent
                context["pending_entities"] = {
                    key: value
                    for key, value in entities.items()
                    if key not in {"product_ids", "product_names"}
                }
                context["pending_product_ids"] = [
                    product.id for product in products[:4]
                ]
                context["pending_product_names"] = [
                    product.name for product in products[:4]
                ]
            elif intent not in {"greeting", "acknowledgement", "out_of_scope"}:
                context.pop("pending_intent", None)
                context.pop("pending_entities", None)
                context.pop("pending_product_ids", None)
                context.pop("pending_product_names", None)
            for key in (
                "budget_min", "budget_max", "category", "brand",
                "ram_gb", "storage_gb", "preference",
            ):
                if key in entities:
                    context[key] = entities[key]
            generated_title = None

            if (
                conversation.title == "New shopping conversation"
                and intent not in {"greeting", "acknowledgement", "out_of_scope"}
            ):
                if intent == "comparison" and len(products) >= 2:
                    generated_title = (
                        f"{products[0].name} vs {products[1].name}"
                        + (f" +{len(products) - 2}" if len(products) > 2 else "")
                    )[:180]
                else:
                    generated_title = (
                        products[0].name
                        if products
                        else payload.content[:80]
                    )

            self.repository.update_context(
                database_session,
                conversation,
                context=context,
                title=generated_title,
            )
            database_session.commit()
        except Exception:
            database_session.rollback()
            raise

        database_session.refresh(conversation)
        database_session.refresh(user_message)
        database_session.refresh(assistant_message)

        return AssistantTurnResponse(
            conversation=ConversationResponse.model_validate(conversation),
            user_message=AssistantMessageResponse.model_validate(user_message),
            assistant_message=(
                AssistantMessageResponse.model_validate(assistant_message)
            ),
        )
