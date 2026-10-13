"""Database operations for assistant conversations and grounding."""

import re
from decimal import Decimal

from sqlalchemy import exists, func, or_, select
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
    "aur",
    "buy",
    "compare",
    "for",
    "history",
    "is",
    "me",
    "of",
    "or",
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
    "ko",
    "kro",
    "karo",
    "mujhe",
    "se",
    "wala",
    "wale",
}


def _normalized_tokens(value: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", value.lower())


def product_search_terms(message: str, *, limit: int = 8) -> list[str]:
    """Return bounded high-signal terms for the product candidate query."""

    terms = [
        token
        for token in _normalized_tokens(message)
        if len(token) >= 2 and token not in STOP_WORDS
    ]
    distinctive = [
        token for token in terms if any(character.isdigit() for character in token)
    ]
    selected = distinctive or terms
    return list(dict.fromkeys(selected))[:limit]


def _phrase_positions(
    message_tokens: list[str],
    phrase_tokens: list[str],
) -> list[int]:
    phrase_length = len(phrase_tokens)
    if not phrase_length or phrase_length > len(message_tokens):
        return []
    return [
        index
        for index in range(len(message_tokens) - phrase_length + 1)
        if message_tokens[index:index + phrase_length] == phrase_tokens
    ]


def rank_product_entity_matches(
    message: str,
    products: list[CanonicalProduct],
    *,
    limit: int = 5,
) -> list[CanonicalProduct]:
    """Resolve explicitly named products without adding longer variants.

    Exact contiguous aliases win over fuzzy token overlap. For example,
    ``Vivo V70`` matches V70 but not V70 FE, while ``iPhone 17 Pro`` matches
    the Pro model without also returning Pro Max or Air. Multiple products
    are returned in the order in which the user named them.
    """

    message_tokens = _normalized_tokens(message)
    if not message_tokens:
        return []

    exact_matches: list[tuple[int, int, CanonicalProduct]] = []
    for product in products:
        aliases: list[list[str]] = []
        for source in (product.name, product.model or ""):
            tokens = _normalized_tokens(source)
            if tokens and tokens not in aliases:
                aliases.append(tokens)
            # Catalog names commonly start with a brand omitted by users:
            # "Apple iPhone 17 Pro" -> "iPhone 17 Pro".
            if len(tokens) >= 3 and tokens[1:] not in aliases:
                aliases.append(tokens[1:])
            # In multi-product comparisons users commonly state the family
            # once: "iPhone 18 Pro Max or 17 Pro Max".  A suffix beginning
            # with a model number is still an exact, high-signal alias and
            # must resolve the second product without fuzzy-matching an older
            # iPhone or pulling a stale recommendation from conversation
            # context.
            numeric_index = next(
                (
                    index
                    for index, token in enumerate(tokens)
                    if any(character.isdigit() for character in token)
                ),
                None,
            )
            if (
                numeric_index is not None
                and len(tokens[numeric_index:]) >= 2
                and tokens[numeric_index:] not in aliases
            ):
                aliases.append(tokens[numeric_index:])

        candidate_matches: list[tuple[int, int]] = []
        for alias in aliases:
            if len(alias) < 2 and not any(char.isdigit() for char in alias[0]):
                continue
            for position in _phrase_positions(message_tokens, alias):
                candidate_matches.append((position, len(alias)))
        if candidate_matches:
            for position, length in set(candidate_matches):
                exact_matches.append((position, length, product))

    if exact_matches:
        # Drop any model mention wholly contained inside a longer matched
        # model mention. This handles aliases whose brand was omitted at a
        # later token, for example "Itel S26 Ultra" appearing inside
        # "Itel Super S26 Ultra". A separately written second product is
        # preserved because its span is outside the longer mention.
        non_contained_matches = []
        for position, length, product in exact_matches:
            end = position + length
            is_contained = any(
                other_position <= position
                and other_position + other_length >= end
                and other_length > length
                for other_position, other_length, _ in exact_matches
            )
            if not is_contained:
                non_contained_matches.append((position, length, product))
        ordered = sorted(
            non_contained_matches,
            key=lambda item: (item[0], -item[1], item[2].name.lower()),
        )
        results = []
        seen_names = set()
        for _, _, product in ordered:
            normalized_name = " ".join(_normalized_tokens(product.name))
            if normalized_name in seen_names:
                continue
            seen_names.add(normalized_name)
            results.append(product)
            if len(results) == limit:
                break
        return results

    terms = [
        term
        for term in message_tokens
        if len(term) >= 2 and term not in STOP_WORDS
    ]
    if not terms:
        return []

    message_terms = set(terms)
    ranked: list[tuple[float, int, CanonicalProduct]] = []
    for product in products:
        searchable = f"{product.name} {product.model or ''}".lower()
        product_terms = set(_normalized_tokens(searchable))
        overlap = message_terms & product_terms
        if not overlap:
            continue

        distinctive = {
            term for term in overlap
            if any(character.isdigit() for character in term)
        }
        if len(overlap) < 2 and not distinctive:
            continue

        coverage = len(overlap) / max(len(product_terms), 1)
        score = len(overlap) * 10 + len(distinctive) * 4 + coverage
        ranked.append((score, len(overlap), product))

    ranked.sort(key=lambda item: (-item[0], -item[1], item[2].name))
    if not ranked:
        return []

    best_score = ranked[0][0]
    return [
        product
        for score, _, product in ranked
        if score >= max(14, best_score * 0.45)
    ][:limit]


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


def extract_processor_evidence(
    specifications: dict[str, object] | None,
    listing_titles: str | None,
) -> str | None:
    """Return catalog-listed processor text without inventing performance.

    Processor names are useful eligibility evidence, but VEXTRO does not
    currently store normalized benchmark scores.  The assistant therefore
    exposes the listed chipset and never pretends that its name alone proves
    which phone is fastest.
    """

    for key, value in (specifications or {}).items():
        normalized_key = str(key).strip().lower()
        if not any(
            term in normalized_key
            for term in ("processor", "chipset", "cpu", "soc")
        ):
            continue
        normalized_value = " ".join(str(value).split()).strip(" ,;|-")
        if normalized_value:
            return normalized_value[:180]

    title = " ".join((listing_titles or "").split())
    match = re.search(
        r"\b(?:snapdragon|dimensity|helio|exynos|tensor|bionic|unisoc)"
        r"(?:\s+[a-z0-9+.-]+){0,3}\b",
        title,
        flags=re.IGNORECASE,
    )
    return match.group(0)[:180] if match else None


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
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[int, list[AssistantConversation]]:
        total = database_session.scalar(
            select(func.count(AssistantConversation.id)).where(
                AssistantConversation.user_id == user_id,
            )
        ) or 0
        statement = (
            select(AssistantConversation)
            .where(AssistantConversation.user_id == user_id)
            .order_by(AssistantConversation.updated_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return int(total), list(database_session.scalars(statement))

    @staticmethod
    def get_conversation(
        database_session: Session,
        *,
        conversation_id: int,
        user_id: int,
        with_messages: bool = False,
        for_update: bool = False,
    ) -> AssistantConversation | None:
        statement = select(AssistantConversation).where(
            AssistantConversation.id == conversation_id,
            AssistantConversation.user_id == user_id,
        )

        if with_messages:
            statement = statement.options(
                selectinload(AssistantConversation.messages),
            )
        if for_update:
            statement = statement.with_for_update()

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
    def list_messages(
        database_session: Session,
        *,
        conversation_id: int,
        limit: int = 100,
        before_message_id: int | None = None,
    ) -> list[AssistantMessage]:
        statement = select(AssistantMessage).where(
            AssistantMessage.conversation_id == conversation_id,
        )
        if before_message_id is not None:
            statement = statement.where(
                AssistantMessage.id < before_message_id,
            )
        statement = statement.order_by(AssistantMessage.id.desc()).limit(limit)
        return list(reversed(list(database_session.scalars(statement))))

    @staticmethod
    def count_messages(
        database_session: Session,
        *,
        conversation_id: int,
        before_message_id: int | None = None,
    ) -> int:
        statement = select(func.count(AssistantMessage.id)).where(
            AssistantMessage.conversation_id == conversation_id,
        )
        if before_message_id is not None:
            statement = statement.where(
                AssistantMessage.id < before_message_id,
            )
        return int(database_session.scalar(statement) or 0)

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

        search_terms = product_search_terms(message)
        if not search_terms:
            return []
        candidate_filters = []
        for term in search_terms:
            pattern = f"%{term}%"
            candidate_filters.extend(
                (
                    CanonicalProduct.name.ilike(pattern),
                    CanonicalProduct.model.ilike(pattern),
                )
            )
        candidate_limit = max(limit * 40, 80)
        statement = (
            select(CanonicalProduct)
            .where(
                CanonicalProduct.is_active.is_(True),
                or_(*candidate_filters),
            )
            .options(selectinload(CanonicalProduct.variants))
            .limit(candidate_limit)
        )
        products = list(database_session.scalars(statement))
        return rank_product_entity_matches(message, products, limit=limit)

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
        requested_fields: list[str] | None = None,
        exclude_ids: list[int] | None = None,
        limit: int = 4,
    ) -> list[dict[str, object]]:
        """Rank available catalog products using live price and rating data."""

        lowest_price = func.min(ProductListing.current_price)
        best_rating = func.max(ProductListing.rating)
        latest_seen_at = func.max(ProductListing.last_seen_at)
        listing_titles = func.string_agg(ProductListing.title, " || ")
        statement = (
            select(
                CanonicalProduct,
                Brand.name.label("brand_name"),
                Category.name.label("category_name"),
                lowest_price.label("lowest_price"),
                best_rating.label("best_rating"),
                latest_seen_at.label("latest_seen_at"),
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
        quality_fields = set(requested_fields or [])
        needs_camera = preference == "camera" or "camera" in quality_fields
        needs_processor = "processor" in quality_fields
        query_limit = (
            500
            if needs_camera or needs_processor
            else max(limit * 5, 20)
        )
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
                "last_seen_at": seen_at.isoformat() if seen_at else None,
                "_specifications": product.specifications or {},
                "_listing_titles": titles,
            }
            for (
                product,
                brand_name,
                category_name,
                price,
                rating,
                seen_at,
                titles,
            ) in rows
        ]

        if needs_camera or needs_processor:
            ranked = []
            for index, item in enumerate(results):
                specifications = item.pop("_specifications")
                titles = item.pop("_listing_titles")
                camera_evidence = extract_camera_evidence(
                    specifications,
                    titles,
                )
                processor_evidence = extract_processor_evidence(
                    specifications,
                    titles,
                )
                if needs_camera and camera_evidence is None:
                    continue
                if needs_processor and processor_evidence is None:
                    continue
                rear_score, front_score, description = (
                    camera_evidence or (0.0, 0.0, "")
                )
                if camera_evidence is not None:
                    item["preference_evidence"] = description
                if processor_evidence is not None:
                    item["processor_evidence"] = processor_evidence
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
