from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Path,
    Query,
    status,
)
from sqlalchemy.orm import Session
from app.schemas.product_comparison import (
    ProductComparisonResponse,
)

from app.core.database import get_db
from app.schemas.product_catalog import (
    ProductDetailResponse,
    ProductListResponse,
    ProductListingsResponse,
)
from app.services.product_catalog_service import (
    get_product_detail,
    get_product_listings_response,
    get_products,
)
from app.services.product_comparison_service import (
    get_product_comparison_response,
)


router = APIRouter(
    prefix="/api/v1/products",
    tags=["products"],
)

@router.get(
    "/compare",
    response_model=ProductComparisonResponse,
    status_code=status.HTTP_200_OK,
)
def compare_products(
    product_ids: list[int] = Query(
        ...,
        min_length=2,
        max_length=3,
        description=(
            "Two or three canonical product IDs "
            "to compare."
        ),
    ),
    database_session: Session = Depends(get_db),
) -> ProductComparisonResponse:
    """Return side-by-side intelligence for selected products."""

    if any(product_id < 1 for product_id in product_ids):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Product IDs must be positive integers.",
        )

    if len(set(product_ids)) != len(product_ids):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Duplicate product IDs are not allowed.",
        )

    result = get_product_comparison_response(
        database_session,
        product_ids,
    )

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="One or more products were not found.",
        )

    return result
@router.get(
    "",
    response_model=ProductListResponse,
    status_code=status.HTTP_200_OK,
)
def list_products(
    database_session: Session = Depends(get_db),
    page: int = Query(
        default=1,
        ge=1,
        description="Requested page number.",
    ),
    page_size: int = Query(
        default=20,
        ge=1,
        le=100,
        description="Number of products returned per page.",
    ),
    search: str | None = Query(
        default=None,
        min_length=1,
        max_length=200,
        description="Search products by name, model, or description.",
    ),
    category_slug: str | None = Query(
        default=None,
        min_length=1,
        max_length=255,
        description="Filter products by category slug.",
    ),
    brand_slug: str | None = Query(
        default=None,
        min_length=1,
        max_length=255,
        description="Filter products by brand slug.",
    ),
) -> ProductListResponse:
    """Return active products with search, filtering, and pagination."""

    return get_products(
        database_session,
        page=page,
        page_size=page_size,
        search=search,
        category_slug=category_slug,
        brand_slug=brand_slug,
    )


@router.get(
    "/{product_id}",
    response_model=ProductDetailResponse,
    status_code=status.HTTP_200_OK,
)
def read_product_detail(
    product_id: int = Path(
        ...,
        ge=1,
        description="Canonical product ID.",
    ),
    database_session: Session = Depends(get_db),
) -> ProductDetailResponse:
    """Return one canonical product with variants and images."""

    product = get_product_detail(
        database_session,
        product_id,
    )

    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )

    return product


@router.get(
    "/{product_id}/listings",
    response_model=ProductListingsResponse,
    status_code=status.HTTP_200_OK,
)
def read_product_listings(
    product_id: int = Path(
        ...,
        ge=1,
        description="Canonical product ID.",
    ),
    database_session: Session = Depends(get_db),
) -> ProductListingsResponse:
    """Return available marketplace listings for one product."""

    result = get_product_listings_response(
        database_session,
        product_id,
    )

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )

    return result