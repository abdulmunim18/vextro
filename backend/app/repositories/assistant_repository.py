"""Database operations for assistant conversations and grounding."""

import re
from decimal import Decimal

from sqlalchemy import exists, func, select
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
    "battery",
    "camera",
    "details",
    "display",
    "feature",
    "features",
    "mobile",
    "phone",
    "processor",
    "ram",
    "rom",
    "spec",
    "specification",
    "specs",
    "storage",
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


def extract_camera_evidence(
    specifications: dict[str, object] | None,
    listing_titles: str | None,
) -> tuple[float, float, str] | None:
    """Return a deterministic camera score and human-readable evidence.

    Seller titles are used only as catalog evidence. The score intentionally
    stays simple and transparent: listed rear/main megapixels first, then front
    megapixels. It is not presented as a lab-quality camera benchmark.
    """

    specs = specifications or {}
    text = (listing_titles or "").lower()

    structured_rear = []
    structured_front = []
    for key, value in specs.items():
        normalized_key = str(key).lower()
        values = [
            float(number)
            for number in re.findall(
                r"(\d+(?:\.\d+)?)\s*mp",
                str(value).lower(),
            )
        ]
        if not values or "camera" not in normalized_key:
            continue
        if any(term in normalized_key for term in ("front", "selfie")):
            structured_front.extend(values)
        elif any(term in normalized_key for term in ("rear", "back", "main")):
            structured_rear.extend(values)

    mp_matches = list(re.finditer(r"(\d+(?:\.\d+)?)\s*mp", text))
    label_matches = list(
        re.finditer(
            r"\b(front|selfie|rear|back|main)(?:\s+camera)?\b",
            text,
        )
    )
    used_mp_indexes: set[int] = set()
    listing_rear: list[float] = []
    listing_front: list[float] = []

    def clean_gap(value: str) -> bool:
        return bool(re.fullmatch(r"[\s:,_+\-/()]*", value))

    for label in label_matches:
        selected_index = None
        for index in range(len(mp_matches) - 1, -1, -1):
            mp_match = mp_matches[index]
            if index in used_mp_indexes or mp_match.end() > label.start():
                continue
            gap = text[mp_match.end():label.start()]
            if len(gap) <= 16 and clean_gap(gap):
                selected_index = index
                break

        if selected_index is None:
            for index, mp_match in enumerate(mp_matches):
                if index in used_mp_indexes or mp_match.start() < label.end():
                    continue
                gap = text[label.end():mp_match.start()]
                if len(gap) <= 16 and clean_gap(gap):
                    selected_index = index
                break

        if selected_index is None:
            continue
        used_mp_indexes.add(selected_index)
        value = float(mp_matches[selected_index].group(1))
        if label.group(1) in {"front", "selfie"}:
            listing_front.append(value)
        else:
            listing_rear.append(value)

    rear_values = structured_rear or listing_rear
    front_values = structured_front or listing_front
    all_values = [
        float(value)
        for value in re.findall(r"(\d+(?:\.\d+)?)\s*mp", text)
    ]
    all_values.extend(structured_rear)
    all_values.extend(structured_front)
    if not all_values:
        return None

    rear = max(rear_values) if rear_values else max(all_values)
    front = max(front_values) if front_values else 0.0
    evidence_parts = [f"listed {rear:g}MP rear/main"]
    if front:
        evidence_parts.append(f"{front:g}MP front")
    return rear, front, " + ".join(evidence_parts)


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
        preference: str | None = None,
        exclude_ids: list[int] | None = None,
        limit: int = 4,
    ) -> list[dict[str, object]]:
        """Rank available catalog products using live price and rating data."""

        lowest_price = func.min(ProductListing.current_price)
        best_rating = func.max(ProductListing.rating)
        listing_titles = func.string_agg(ProductListing.title, " || ")
        statement = (
            select(
                CanonicalProduct,
                Brand.name.label("brand_name"),
                Category.name.label("category_name"),
                lowest_price.label("lowest_price"),
                best_rating.label("best_rating"),
                listing_titles.label("listing_titles"),
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
            normalized_category = category.strip().lower()
            category_aliases = {
                "mobile phones": {"mobile phones", "smartphones"},
                "smartphones": {"mobile phones", "smartphones"},
            }.get(normalized_category)
            if category_aliases:
                statement = statement.where(
                    func.lower(Category.name).in_(category_aliases)
                )
            else:
                statement = statement.where(
                    Category.name.ilike(f"%{category}%")
                )
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

        if budget_max is not None:
            # Budget fit is the primary signal. Rating-first ordering allowed
            # cheap feature phones to outrank suitable phones near the limit.
            ordering = (
                lowest_price.desc(),
                best_rating.desc().nullslast(),
                CanonicalProduct.name.asc(),
            )
        else:
            ordering = (
                best_rating.desc().nullslast(),
                lowest_price.desc(),
                CanonicalProduct.name.asc(),
            )
        query_limit = 500 if preference == "camera" else max(limit * 5, 20)
        statement = statement.order_by(*ordering).limit(query_limit)

        rows = database_session.execute(statement).all()
        results = [
            {
                "id": product.id,
                "name": product.name,
                "model": product.model,
                "brand": brand_name,
                "category": category_name,
                "lowest_price": str(price),
                "rating": str(rating) if rating is not None else None,
                "_specifications": product.specifications or {},
                "_listing_titles": titles,
            }
            for product, brand_name, category_name, price, rating, titles in rows
        ]

        if preference == "camera":
            ranked = []
            for index, item in enumerate(results):
                evidence = extract_camera_evidence(
                    item.pop("_specifications"),
                    item.pop("_listing_titles"),
                )
                if evidence is None:
                    continue
                rear_score, front_score, description = evidence
                item["preference_evidence"] = description
                ranked.append((rear_score, front_score, -index, item))

            ranked.sort(key=lambda row: (-row[0], -row[1], -row[2]))
            deduplicated = []
            seen_names = set()
            for _, _, _, item in ranked:
                normalized_name = str(item["name"]).strip().lower()
                if normalized_name in seen_names:
                    continue
                seen_names.add(normalized_name)
                deduplicated.append(item)
                if len(deduplicated) == limit:
                    break
            return deduplicated

        for item in results:
            item.pop("_specifications", None)
            item.pop("_listing_titles", None)
        deduplicated = []
        seen_names = set()
        for item in results:
            normalized_name = str(item["name"]).strip().lower()
            if normalized_name in seen_names:
                continue
            seen_names.add(normalized_name)
            deduplicated.append(item)
            if len(deduplicated) == limit:
                break
        return deduplicated

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
                # An alternative the shopper cannot buy is not one.
                exists(
                    select(ProductListing.id)
                    .join(
                        ProductVariant,
                        ProductVariant.id
                        == ProductListing.product_variant_id,
                    )
                    .where(
                        ProductVariant.canonical_product_id
                        == CanonicalProduct.id,
                        ProductListing.is_available.is_(True),
                    )
                ),
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
