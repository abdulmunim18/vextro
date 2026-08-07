from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models.brand import Brand
from app.models.canonical_product import CanonicalProduct
from app.models.category import Category
from app.models.product_listing import ProductListing
from app.models.product_variant import ProductVariant


def list_products(
    database_session: Session,
    *,
    page: int,
    page_size: int,
    search: str | None = None,
    category_slug: str | None = None,
    brand_slug: str | None = None,
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

    total = database_session.scalar(
        count_query.where(*filters)
    ) or 0

    offset = (page - 1) * page_size

    products = list(
        database_session.scalars(
            products_query
            .where(*filters)
            .order_by(
                CanonicalProduct.name.asc(),
                CanonicalProduct.id.asc(),
            )
            .offset(offset)
            .limit(page_size)
        ).all()
    )

    return products, total


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