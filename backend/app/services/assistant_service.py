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


INTENT_PATTERNS = (
    ("set_price_alert", r"\b(alert|notify|notification|yaad dilana)\b|bata dena"),
    ("comparison", r"\b(compare|comparison|versus|vs|difference|better)\b|muqabla|farq"),
    ("price_history", r"\b(history|historical|trend|ever)\b|pehle ki (price|qeemat)|price record"),
    ("buy_or_wait", r"buy now|should i buy|\bwait\b|best time|ab (loon|kharidon)|intezar"),
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
    ("greeting", r"^(hi|hello|hey|salam|assalam|help)\b"),
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

    return "product_search"


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

    storage_match = re.search(
        r"\b(\d{2,4})\s*gb\s*(?:storage|rom)\b|\b(?:storage|rom)\s*(\d{2,4})\s*gb",
        normalized,
    )
    if storage_match:
        entities["storage_gb"] = int(
            next(value for value in storage_match.groups() if value)
        )

    reference_patterns = (
        ("second", r"\b(second|2nd|dusra|doosra|dusre)\b"),
        ("first", r"\b(first|1st|pehla|pehle)\b"),
        ("current", r"\b(this|it|its|that|is ka|iski|iska|iss|uska|yeh|ye)\b"),
    )
    for reference, pattern in reference_patterns:
        if re.search(pattern, normalized):
            entities["reference"] = reference
            break

    return entities


def inherit_recommendation_context(
    entities: dict[str, object],
    context: dict[str, object],
) -> dict[str, object]:
    """Carry filters only from the immediately relevant recommendation turn."""

    if context.get("last_intent") != "recommendation":
        return entities

    merged = dict(entities)
    has_new_budget = "budget_min" in entities or "budget_max" in entities
    keys = (
        ("category",)
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
    """Extract the last plausible numeric target from an alert request."""

    candidates = _money_candidates(message)

    if not candidates:
        return None

    value = candidates[-1]
    return value if value > 0 else None


class AssistantService:
    """Store conversations and answer only from VEXTRO data."""

    def __init__(
        self,
        repository: AssistantRepository | None = None,
    ) -> None:
        self.repository = repository or AssistantRepository()

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
    ) -> ConversationListResponse:
        conversations = self.repository.list_conversations(
            database_session,
            user_id=user_id,
        )
        return ConversationListResponse(
            total=len(conversations),
            items=[
                ConversationResponse.model_validate(conversation)
                for conversation in conversations
            ],
        )

    def get_conversation(
        self,
        database_session: Session,
        *,
        conversation_id: int,
        user_id: int,
    ) -> ConversationDetailResponse:
        conversation = self.repository.get_conversation(
            database_session,
            conversation_id=conversation_id,
            user_id=user_id,
            with_messages=True,
        )

        if conversation is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="The requested conversation was not found.",
            )

        return ConversationDetailResponse.model_validate(conversation)

    def _resolve_products(
        self,
        database_session: Session,
        *,
        message: str,
        intent: str,
        entities: dict[str, object],
        context: dict[str, object],
    ):
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
        context_ids = [
            int(product_id)
            for product_id in context.get("product_ids", [])
            if str(product_id).isdigit()
        ]
        contextual_products = self.repository.get_products_by_ids(
            database_session, context_ids
        )

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

        reference = entities.get("reference")
        if intent != "comparison" and contextual_products:
            if reference == "second" and len(contextual_products) >= 2:
                return [contextual_products[1]]
            if reference in {"first", "current"}:
                return [contextual_products[0]]

        if intent == "comparison" and explicit_products:
            combined = list(explicit_products)
            existing_ids = {product.id for product in combined}
            for product in contextual_products:
                if product.id not in existing_ids:
                    combined.append(product)
            return combined[:3]

        if explicit_products:
            return explicit_products
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
        timestamp = datetime.now(timezone.utc).isoformat()

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
                    "data_timestamp": timestamp,
                },
            )

        if intent == "acknowledgement":
            return (
                "Ji. Aap product ki price, specifications, comparison, "
                "price history ya apne budget ke andar recommendation "
                "pooch sakte hain.",
                {
                    "matched_products": [],
                    "data_timestamp": timestamp,
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
            return (
                "I could not match that request to an active VEXTRO "
                "catalog product. Please include a brand and model, for "
                "example 'Samsung Galaxy A55'.",
                {"matched_products": [], "data_timestamp": timestamp},
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

            comparison = get_product_comparison_response(
                database_session,
                [product.id for product in products[:3]],
            )
            assert comparison is not None
            summary = comparison.summary
            content = (
                f"Compared {comparison.total} products. "
                f"{summary.cheapest_product_name} currently has the "
                f"lowest offer at PKR {summary.lowest_current_price}. "
                f"The observed price gap is PKR {summary.price_gap}."
            )
            return content, comparison.model_dump(mode="json")

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
            target_price = _extract_target_price(message)

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

            specification_parts = [
                f"{key}: {value}"
                for key, value in (product.specifications or {}).items()
                if value not in (None, "", [], {})
            ][:6]
            variant_parts = []
            for variant in variants[:4]:
                values = []
                if variant["ram_gb"]:
                    values.append(f"{variant['ram_gb']}GB RAM")
                if variant["storage_gb"]:
                    values.append(f"{variant['storage_gb']}GB storage")
                if variant["color"]:
                    values.append(str(variant["color"]))
                if values:
                    variant_parts.append(" / ".join(values))
            detail_text = "; ".join(specification_parts + variant_parts)
            if not detail_text:
                detail_text = "No structured specifications are stored yet"
            return (
                f"{product.name}: {detail_text}.",
                {
                    "matched_products": matched,
                    "specifications": product.specifications or {},
                    "variants": variants,
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
        )

        if conversation is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="The requested conversation was not found.",
            )

        intent = detect_assistant_intent(payload.content)
        entities = extract_assistant_entities(payload.content)
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
            )
        products = self._resolve_products(
            database_session,
            message=payload.content,
            intent=intent,
            entities=entities,
            context=conversation.context,
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
            data_timestamp = datetime.now(timezone.utc)
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
            context = {
                **conversation.context,
                "product_ids": remembered_ids[:4],
                "last_intent": (
                    conversation.context.get("last_intent")
                    if intent == "acknowledgement"
                    else intent
                ),
            }
            for key in (
                "budget_min", "budget_max", "category", "brand",
                "ram_gb", "storage_gb", "preference",
            ):
                if key in entities:
                    context[key] = entities[key]
            generated_title = None

            if conversation.title == "New shopping conversation":
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
