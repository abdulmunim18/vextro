from math import ceil

from sqlalchemy.orm import Session

from app.repositories.product_catalog_repository import (
    get_product_by_id,
    list_product_listings,
    list_products,
    get_product_listing_summaries,
)
from app.schemas.product_catalog import (
    ProductDetailResponse,
    ProductListItemResponse,
    ProductListResponse,
    ProductListingResponse,
    ProductListingsResponse,
)


def get_products(
    database_session: Session,
    *,
    page: int,
    page_size: int,
    search: str | None = None,
    category_slug: str | None = None,
    brand_slug: str | None = None,
    min_price=None,
    max_price=None,
    platform_code: str | None = None,
    min_rating=None,
    is_available: bool | None = None,
    sort_by: str = "name_asc",
) -> ProductListResponse:
    """Return a paginated and filtered product catalog response."""

    products, total = list_products(
        database_session,
        page=page,
        page_size=page_size,
        search=search,
        category_slug=category_slug,
        brand_slug=brand_slug,
        min_price=min_price,
        max_price=max_price,
        platform_code=platform_code,
        min_rating=min_rating,
        is_available=is_available,
        sort_by=sort_by,
    )

    summaries = get_product_listing_summaries(
        database_session,
        [product.id for product in products],
    )

    total_pages = ceil(total / page_size) if total > 0 else 0

    return ProductListResponse(
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        items=[
            ProductListItemResponse.model_validate(product).model_copy(
                update=summaries.get(product.id, {}),
            )
            for product in products
        ],
    )


def get_product_detail(
    database_session: Session,
    product_id: int,
) -> ProductDetailResponse | None:
    """Return one active product or None when it does not exist."""

    product = get_product_by_id(
        database_session,
        product_id,
    )

    if product is None:
        return None

    return ProductDetailResponse.model_validate(product)


def get_product_listings_response(
    database_session: Session,
    product_id: int,
) -> ProductListingsResponse | None:
    """Return available marketplace listings for one active product."""

    product = get_product_by_id(
        database_session,
        product_id,
    )

    if product is None:
        return None

    listings = list_product_listings(
        database_session,
        product_id,
    )

    listing_responses = [
        ProductListingResponse.model_validate(listing)
        for listing in listings
    ]

    return ProductListingsResponse(
        product_id=product.id,
        product_name=product.name,
        total=len(listing_responses),
        items=listing_responses,
    )
