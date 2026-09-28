"""Database operations for assistant conversations and grounding."""

import re
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.assistant_conversation import AssistantConversation
from app.models.assistant_message import AssistantMessage
from app.models.canonical_product import CanonicalProduct
from app.models.brand import Brand
from app.models.category import Category
from app.models.product_listing import ProductListing
from app.models.product_variant import ProductVariant


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
    "ab",
    "andar",
    "batao",
    "dikhao",
    "ka",
    "ke",
    "ki",
    "koi",
    "konsa",
    "konsi",
    "mujhe",
    "se",
    "wala",
    "wale",
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
        """Find explicitly named products, ranked by token coverage.

        The previous query returned any product containing any message word,
        so generic words such as ``phone`` could displace the actual model.
        Catalog size is modest, therefore deterministic in-memory scoring gives
        much better multi-product extraction without an external AI service.
        """

        terms = [
            term
            for term in re.findall(r"[a-zA-Z0-9]+", message.lower())
            if len(term) >= 2 and term not in STOP_WORDS
        ]

        if not terms:
            return []

        statement = (
            select(CanonicalProduct)
            .where(CanonicalProduct.is_active.is_(True))
            .options(selectinload(CanonicalProduct.variants))
        )
        products = list(database_session.scalars(statement))
        message_terms = set(terms)
        ranked: list[tuple[float, int, CanonicalProduct]] = []

        for product in products:
            searchable = f"{product.name} {product.model or ''}".lower()
            product_terms = set(re.findall(r"[a-z0-9]+", searchable))
            overlap = message_terms & product_terms

            if not overlap:
                continue

            model_terms = set(
                re.findall(r"[a-z0-9]+", (product.model or "").lower())
            )
            distinctive = {
                term for term in overlap
                if any(character.isdigit() for character in term)
                or term in model_terms
            }
            # One brand/family word alone is ambiguous. A model token, two
            # matching words, or the complete name is treated as explicit.
            if len(overlap) < 2 and not distinctive:
                continue

            coverage = len(overlap) / max(len(product_terms), 1)
            score = len(overlap) * 10 + len(distinctive) * 4 + coverage
            if product.name.lower() in message.lower():
                score += 30
            ranked.append((score, len(overlap), product))

        ranked.sort(key=lambda item: (-item[0], -item[1], item[2].name))
        if not ranked:
            return []

        # Keep products reasonably close to the strongest explicit match. This
        # retains two named products for comparisons without returning every
        # phone that happens to share "Galaxy" or "iPhone".
        best_score = ranked[0][0]
        return [
            product
            for score, _, product in ranked
            if score >= max(14, best_score * 0.45)
        ][:limit]

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
        products = list(database_session.scalars(statement))
        by_id = {product.id: product for product in products}
        return [by_id[product_id] for product_id in product_ids if product_id in by_id]

    @staticmethod
    def recommend_products(
        database_session: Session,
        *,
        category: str | None = None,
        brand: str | None = None,
        budget_min: Decimal | None = None,
        budget_max: Decimal | None = None,
        ram_gb: int | None = None,
        storage_gb: int | None = None,
        exclude_ids: list[int] | None = None,
        limit: int = 4,
    ) -> list[dict[str, object]]:
        """Rank available catalog products using live price and rating data."""

        lowest_price = func.min(ProductListing.current_price)
        best_rating = func.max(ProductListing.rating)
        statement = (
            select(
                CanonicalProduct,
                Brand.name.label("brand_name"),
                Category.name.label("category_name"),
                lowest_price.label("lowest_price"),
                best_rating.label("best_rating"),
            )
            .join(Category, Category.id == CanonicalProduct.category_id)
            .outerjoin(Brand, Brand.id == CanonicalProduct.brand_id)
            .join(
                ProductVariant,
                ProductVariant.canonical_product_id == CanonicalProduct.id,
            )
            .join(
                ProductListing,
                ProductListing.product_variant_id == ProductVariant.id,
            )
            .where(
                CanonicalProduct.is_active.is_(True),
                ProductVariant.is_active.is_(True),
                ProductListing.is_available.is_(True),
            )
            .group_by(CanonicalProduct.id, Brand.name, Category.name)
        )

        if category:
            statement = statement.where(Category.name.ilike(f"%{category}%"))
        if brand:
            statement = statement.where(Brand.name.ilike(f"%{brand}%"))
        if ram_gb is not None:
            statement = statement.where(ProductVariant.ram_gb >= ram_gb)
        if storage_gb is not None:
            statement = statement.where(
                ProductVariant.storage_gb >= storage_gb
            )
        if exclude_ids:
            statement = statement.where(CanonicalProduct.id.not_in(exclude_ids))
        if budget_min is not None:
            statement = statement.having(lowest_price >= budget_min)
        if budget_max is not None:
            statement = statement.having(lowest_price <= budget_max)

        statement = statement.order_by(
            best_rating.desc().nullslast(),
            lowest_price.asc(),
            CanonicalProduct.name.asc(),
        ).limit(limit)

        return [
            {
                "id": product.id,
                "name": product.name,
                "model": product.model,
                "brand": brand_name,
                "category": category_name,
                "lowest_price": str(price),
                "rating": str(rating) if rating is not None else None,
            }
            for product, brand_name, category_name, price, rating
            in database_session.execute(statement).all()
        ]

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
