from decimal import Decimal

from sqlalchemy import exists, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models.brand import Brand
from app.models.canonical_product import CanonicalProduct
from app.models.category import Category
from app.models.product_listing import ProductListing
from app.models.product_variant import ProductVariant
from app.models.platform import Platform


def list_products(
    database_session: Session,
    *,
    page: int,
    page_size: int,
    search: str | None = None,
    category_slug: str | None = None,
    brand_slug: str | None = None,
    min_price: Decimal | None = None,
    max_price: Decimal | None = None,
    platform_code: str | None = None,
    min_rating: Decimal | None = None,
    is_available: bool | None = None,
    sort_by: str = "name_asc",
) -> tuple[list[CanonicalProduct], int]:
    """Return active products with pagination and optional filters."""

    products_query = select(CanonicalProduct)
    count_query = select(func.count(CanonicalProduct.id))

    filters = [
        CanonicalProduct.is_active.is_(True),
    ]

    if category_slug:
        products_query = products_query.join(
            Category,
            CanonicalProduct.category_id == Category.id,
        )

        count_query = count_query.join(
            Category,
            CanonicalProduct.category_id == Category.id,
        )

        filters.append(Category.slug == category_slug)

    if brand_slug:
        products_query = products_query.join(
            Brand,
            CanonicalProduct.brand_id == Brand.id,
        )

        count_query = count_query.join(
            Brand,
            CanonicalProduct.brand_id == Brand.id,
        )

        filters.append(Brand.slug == brand_slug)

    if search:
        cleaned_search = search.strip()

        if cleaned_search:
            search_pattern = f"%{cleaned_search}%"

            filters.append(
                or_(
                    CanonicalProduct.name.ilike(search_pattern),
                    CanonicalProduct.model.ilike(search_pattern),
                    CanonicalProduct.description.ilike(search_pattern),
                )
            )

    listing_conditions = [
        ProductVariant.canonical_product_id
        == CanonicalProduct.id,
        ProductVariant.is_active.is_(True),
    ]

    if min_price is not None:
        listing_conditions.append(
            ProductListing.current_price >= min_price,
        )

    if max_price is not None:
        listing_conditions.append(
            ProductListing.current_price <= max_price,
        )

    if min_rating is not None:
        listing_conditions.append(
            ProductListing.rating >= min_rating,
        )

    if is_available is not None:
        listing_conditions.append(
            ProductListing.is_available == is_available,
        )

    listing_filter_query = (
        select(ProductListing.id)
        .join(
            ProductVariant,
            ProductVariant.id
            == ProductListing.product_variant_id,
        )
    )

    if platform_code:
        listing_filter_query = listing_filter_query.join(
            Platform,
            Platform.id == ProductListing.platform_id,
        )
        listing_conditions.append(
            Platform.code == platform_code,
        )

    if any(
        value is not None
        for value in (
            min_price,
            max_price,
            platform_code,
            min_rating,
            is_available,
        )
    ):
        filters.append(
            exists(
                listing_filter_query.where(*listing_conditions)
            )
        )

    total = database_session.scalar(
        count_query.where(*filters)
    ) or 0

    offset = (page - 1) * page_size

    price_sort = (
        select(func.min(ProductListing.current_price))
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
        .correlate(CanonicalProduct)
        .scalar_subquery()
    )
    rating_sort = (
        select(func.max(ProductListing.rating))
        .join(
            ProductVariant,
            ProductVariant.id
            == ProductListing.product_variant_id,
        )
        .where(
            ProductVariant.canonical_product_id
            == CanonicalProduct.id,
        )
        .correlate(CanonicalProduct)
        .scalar_subquery()
    )
    order_map = {
        "name_asc": (CanonicalProduct.name.asc(),),
        "name_desc": (CanonicalProduct.name.desc(),),
        "price_asc": (price_sort.asc().nulls_last(),),
        "price_desc": (price_sort.desc().nulls_last(),),
        "rating_desc": (rating_sort.desc().nulls_last(),),
        "newest": (CanonicalProduct.created_at.desc(),),
    }
    products = list(
        database_session.scalars(
            products_query
            .where(*filters)
            .order_by(*order_map[sort_by], CanonicalProduct.id.asc())
            .offset(offset)
            .limit(page_size)
        ).all()
    )

    return products, total


def get_product_listing_summaries(
    database_session: Session,
    product_ids: list[int],
) -> dict[int, dict[str, object]]:
    """Return compact marketplace metrics for catalog cards."""

    if not product_ids:
        return {}

    statement = (
        select(
            ProductVariant.canonical_product_id,
            ProductListing.current_price,
            ProductListing.rating,
            ProductListing.is_available,
            Platform.code,
        )
        .join(
            ProductListing,
            ProductListing.product_variant_id
            == ProductVariant.id,
        )
        .join(
            Platform,
            Platform.id == ProductListing.platform_id,
        )
        .where(
            ProductVariant.canonical_product_id.in_(product_ids),
            ProductVariant.is_active.is_(True),
        )
    )
    summaries: dict[int, dict[str, object]] = {
        product_id: {
            "lowest_price": None,
            "highest_rating": None,
            "available_listing_count": 0,
            "platform_codes": set(),
        }
        for product_id in product_ids
    }

    for product_id, price, rating, available, code in (
        database_session.execute(statement)
    ):
        summary = summaries[product_id]
        summary["platform_codes"].add(code)

        if rating is not None and (
            summary["highest_rating"] is None
            or rating > summary["highest_rating"]
        ):
            summary["highest_rating"] = rating

        if available:
            summary["available_listing_count"] += 1

            if (
                summary["lowest_price"] is None
                or price < summary["lowest_price"]
            ):
                summary["lowest_price"] = price

    for summary in summaries.values():
        summary["platform_codes"] = sorted(summary["platform_codes"])

    return summaries


def get_product_by_id(
    database_session: Session,
    product_id: int,
) -> CanonicalProduct | None:
    """Return one active product with variants and product images."""

    query = (
        select(CanonicalProduct)
        .options(
            selectinload(CanonicalProduct.variants),
            selectinload(CanonicalProduct.images),
        )
        .where(
            CanonicalProduct.id == product_id,
            CanonicalProduct.is_active.is_(True),
        )
    )

    return database_session.scalar(query)


def list_product_listings(
    database_session: Session,
    product_id: int,
) -> list[ProductListing]:
    """Return available marketplace listings for one canonical product."""

    query = (
        select(ProductListing)
        .join(
            ProductVariant,
            ProductListing.product_variant_id == ProductVariant.id,
        )
        .options(
            selectinload(ProductListing.seller),
            selectinload(ProductListing.images),
        )
        .where(
            ProductVariant.canonical_product_id == product_id,
            ProductVariant.is_active.is_(True),
            ProductListing.is_available.is_(True),
        )
        .order_by(
            ProductListing.current_price.asc(),
            ProductListing.id.asc(),
        )
    )

    return list(
        database_session.scalars(query).all()
    )
