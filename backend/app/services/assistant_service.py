"""Grounded, deterministic conversational shopping assistant."""

import re
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.repositories.assistant_repository import AssistantRepository
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
    ("set_price_alert", ("alert", "notify", "notification")),
    ("comparison", ("compare", " versus ", " vs ", "difference")),
    ("price_history", ("history", "historical", "trend", "ever")),
    ("buy_or_wait", ("buy now", "should i buy", "wait", "best time")),
    ("recommendation", ("recommend", "suggest", "similar", "alternative")),
    ("lowest_price", ("lowest", "cheapest", "current price", "price")),
)


def detect_assistant_intent(message: str) -> str:
    """Classify one supported assistant intent without inventing data."""

    normalized = f" {message.strip().lower()} "

    for intent, phrases in INTENT_PATTERNS:
        if any(phrase in normalized for phrase in phrases):
            return intent

    return "product_search"


def _extract_target_price(message: str) -> Decimal | None:
    """Extract the last plausible numeric target from an alert request."""

    candidates = re.findall(
        r"(?:pkr|rs\.?)?\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)",
        message.lower(),
    )

    if not candidates:
        return None

    value = Decimal(candidates[-1].replace(",", ""))
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
        context: dict[str, object],
    ):
        products = self.repository.find_product_entities(
            database_session,
            message,
        )

        if products:
            return products

        context_ids = [
            int(product_id)
            for product_id in context.get("product_ids", [])
            if str(product_id).isdigit()
        ]
        return self.repository.get_products_by_ids(
            database_session,
            context_ids,
        )

    def _build_answer(
        self,
        database_session: Session,
        *,
        user_id: int,
        intent: str,
        message: str,
        products,
    ) -> tuple[str, dict[str, object]]:
        timestamp = datetime.now(timezone.utc).isoformat()

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

        if intent == "recommendation":
            similar = self.repository.find_similar_products(
                database_session,
                product,
            )
            names = [item.name for item in similar]

            if not names:
                return (
                    f"No active alternatives are currently stored for "
                    f"{product.name}.",
                    {"matched_products": matched, "recommendations": []},
                )

            return (
                f"Catalog alternatives to {product.name}: "
                + ", ".join(names)
                + ". These are category-based cold-start suggestions.",
                {
                    "matched_products": matched,
                    "recommendations": [
                        {"id": item.id, "name": item.name}
                        for item in similar
                    ],
                    "method": "category-based cold-start",
                },
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
        products = self._resolve_products(
            database_session,
            message=payload.content,
            context=conversation.context,
        )
        entities = {
            "product_ids": [product.id for product in products],
            "product_names": [product.name for product in products],
        }
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
            context = {
                **conversation.context,
                "product_ids": entities["product_ids"],
                "last_intent": intent,
            }
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
