"""Database operations for assistant conversations and grounding."""

import re

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.models.assistant_conversation import AssistantConversation
from app.models.assistant_message import AssistantMessage
from app.models.canonical_product import CanonicalProduct


STOP_WORDS = {
    "a",
    "an",
    "and",
    "buy",
    "compare",
    "for",
    "history",
    "is",
    "me",
    "of",
    "price",
    "product",
    "show",
    "the",
    "to",
    "vs",
    "what",
    "with",
}


class AssistantRepository:
    """Persist conversations and find product entities."""

    @staticmethod
    def create_conversation(
        database_session: Session,
        *,
        user_id: int,
        title: str,
    ) -> AssistantConversation:
        conversation = AssistantConversation(
            user_id=user_id,
            title=title,
            context={},
        )
        database_session.add(conversation)
        database_session.flush()
        return conversation

    @staticmethod
    def list_conversations(
        database_session: Session,
        *,
        user_id: int,
    ) -> list[AssistantConversation]:
        statement = (
            select(AssistantConversation)
            .where(AssistantConversation.user_id == user_id)
            .order_by(AssistantConversation.updated_at.desc())
        )
        return list(database_session.scalars(statement))

    @staticmethod
    def get_conversation(
        database_session: Session,
        *,
        conversation_id: int,
        user_id: int,
        with_messages: bool = False,
    ) -> AssistantConversation | None:
        statement = select(AssistantConversation).where(
            AssistantConversation.id == conversation_id,
            AssistantConversation.user_id == user_id,
        )

        if with_messages:
            statement = statement.options(
                selectinload(AssistantConversation.messages),
            )

        return database_session.scalar(statement)

    @staticmethod
    def add_message(
        database_session: Session,
        *,
        conversation_id: int,
        role: str,
        content: str,
        intent: str | None = None,
        entities: dict[str, object] | None = None,
        grounded_data: dict[str, object] | None = None,
        data_timestamp=None,
    ) -> AssistantMessage:
        message = AssistantMessage(
            conversation_id=conversation_id,
            role=role,
            content=content,
            intent=intent,
            entities=entities or {},
            grounded_data=grounded_data or {},
            data_timestamp=data_timestamp,
        )
        database_session.add(message)
        database_session.flush()
        return message

    @staticmethod
    def find_product_entities(
        database_session: Session,
        message: str,
        *,
        limit: int = 5,
    ) -> list[CanonicalProduct]:
        """Find active products using meaningful words from a message."""

        terms = [
            term
            for term in re.findall(r"[a-zA-Z0-9]+", message.lower())
            if len(term) >= 2 and term not in STOP_WORDS
        ]

        if not terms:
            return []

        conditions = [
            or_(
                CanonicalProduct.name.ilike(f"%{term}%"),
                CanonicalProduct.model.ilike(f"%{term}%"),
            )
            for term in terms[:8]
        ]
        statement = (
            select(CanonicalProduct)
            .where(
                CanonicalProduct.is_active.is_(True),
                or_(*conditions),
            )
            .order_by(CanonicalProduct.name.asc())
            .limit(limit)
        )
        return list(database_session.scalars(statement))

    @staticmethod
    def get_products_by_ids(
        database_session: Session,
        product_ids: list[int],
    ) -> list[CanonicalProduct]:
        if not product_ids:
            return []

        statement = (
            select(CanonicalProduct)
            .where(
                CanonicalProduct.id.in_(product_ids),
                CanonicalProduct.is_active.is_(True),
            )
            .order_by(CanonicalProduct.name.asc())
        )
        return list(database_session.scalars(statement))

    @staticmethod
    def find_similar_products(
        database_session: Session,
        product: CanonicalProduct,
        *,
        limit: int = 4,
    ) -> list[CanonicalProduct]:
        """Return deterministic catalog alternatives for cold-start use."""

        statement = (
            select(CanonicalProduct)
            .where(
                CanonicalProduct.is_active.is_(True),
                CanonicalProduct.id != product.id,
                CanonicalProduct.category_id == product.category_id,
            )
            .order_by(
                (
                    CanonicalProduct.brand_id == product.brand_id
                ).desc(),
                CanonicalProduct.name.asc(),
            )
            .limit(limit)
        )
        return list(database_session.scalars(statement))

    @staticmethod
    def update_context(
        database_session: Session,
        conversation: AssistantConversation,
        *,
        context: dict[str, object],
        title: str | None = None,
    ) -> None:
        conversation.context = context

        if title is not None:
            conversation.title = title

        database_session.flush()
