from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Path,
    Query,
    status,
)
from decimal import Decimal
from typing import Literal
from sqlalchemy.orm import Session
from app.api.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.product_comparison import (
    ProductComparisonResponse,
)

from app.core.database import get_db
from app.schemas.product_catalog import (
    ProductDetailResponse,
    ProductListResponse,
    ProductListingsResponse,
)
from app.schemas.reviews import ProductReviewsResponse
from app.schemas.review_analysis import ProductReviewAnalysisResponse, ReviewAnalysisResponse
from app.schemas.seller_trust import SellerTrustResponse
from app.services.product_catalog_service import (
    get_product_detail,
    get_product_listings_response,
    get_products,
)
from app.services.product_comparison_service import (
    get_product_comparison_response,
)
from app.services.review_service import ReviewService
from app.services.review_analysis_service import ReviewAnalysisService
from app.services.seller_trust_service import SellerTrustService
from app.models.product_listing import ProductListing


router = APIRouter(
    prefix="/api/v1/products",
    tags=["products"],
)
review_service = ReviewService()
review_analysis_service = ReviewAnalysisService()
seller_trust_service = SellerTrustService()

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
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Product IDs must be positive integers.",
        )

    if len(set(product_ids)) != len(product_ids):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
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
    min_price: Decimal | None = Query(
        default=None,
        ge=0,
        description="Minimum marketplace listing price.",
    ),
    max_price: Decimal | None = Query(
        default=None,
        ge=0,
        description="Maximum marketplace listing price.",
    ),
    platform_code: str | None = Query(
        default=None,
        pattern="^[a-z0-9-]+$",
        max_length=50,
    ),
    min_rating: Decimal | None = Query(
        default=None,
        ge=0,
        le=5,
    ),
    is_available: bool | None = Query(default=None),
    sort_by: Literal[
        "name_asc",
        "name_desc",
        "price_asc",
        "price_desc",
        "rating_desc",
        "newest",
    ] = Query(default="name_asc"),
) -> ProductListResponse:
    """Return active products with search, filtering, and pagination."""

    if (
        min_price is not None
        and max_price is not None
        and min_price > max_price
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="min_price cannot be greater than max_price.",
        )

    return get_products(
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
    """Return marketplace listings for one product."""

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


@router.get(
    "/{product_id}/reviews",
    response_model=ProductReviewsResponse,
    status_code=status.HTTP_200_OK,
)
def read_product_reviews(
    product_id: int = Path(..., ge=1),
    listing_id: int | None = Query(default=None, ge=1),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    database_session: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> ProductReviewsResponse:
    """Return persisted reviews and factual rating aggregates."""

    return review_service.get_product_reviews(
        database_session,
        product_id=product_id,
        listing_id=listing_id,
        page=page,
        page_size=page_size,
    )


@router.get("/{product_id}/review-analysis", response_model=ProductReviewAnalysisResponse)
def read_product_review_analysis(
    product_id: int = Path(..., ge=1),
    listing_id: int | None = Query(default=None, ge=1),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    database_session: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> ProductReviewAnalysisResponse:
    """Read persisted suspicion evidence; scores are not fraud labels."""
    return review_analysis_service.product_summary(
        database_session, product_id=product_id, listing_id=listing_id,
        page=page, page_size=page_size,
    )


@router.post("/{product_id}/review-analysis/run", response_model=ProductReviewAnalysisResponse)
def rerun_product_review_analysis(
    product_id: int = Path(..., ge=1),
    listing_id: int = Query(..., ge=1),
    database_session: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> ProductReviewAnalysisResponse:
    """Recalculate one product listing, including reviews predating v1."""
    from app.repositories.review_repository import ReviewRepository

    repository = ReviewRepository()
    if repository.get_product(database_session, product_id) is None:
        raise HTTPException(status_code=404, detail="Product not found")
    if not repository.listing_belongs_to_product(database_session, listing_id=listing_id, product_id=product_id):
        raise HTTPException(status_code=404, detail="Listing not found for this product")
    try:
        review_analysis_service.analyze_listing(database_session, listing_id)
        listing = database_session.get(ProductListing, listing_id)
        if listing is not None and listing.seller_id is not None:
            seller_trust_service.recalculate(database_session, listing.seller_id)
        database_session.commit()
    except Exception:
        database_session.rollback()
        raise
    return review_analysis_service.product_summary(
        database_session, product_id=product_id, listing_id=listing_id,
        page=1, page_size=20,
    )


@router.get("/{product_id}/reviews/{review_id}/analysis", response_model=ReviewAnalysisResponse)
def read_review_analysis(
    product_id: int = Path(..., ge=1),
    review_id: int = Path(..., ge=1),
    database_session: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> ReviewAnalysisResponse:
    """Read versioned evidence for one review belonging to a product."""
    return review_analysis_service.product_review_result(
        database_session, product_id=product_id, review_id=review_id,
    )


@router.get("/{product_id}/listings/{listing_id}/seller-trust", response_model=SellerTrustResponse)
def read_listing_seller_trust(
    product_id: int = Path(..., ge=1),
    listing_id: int = Path(..., ge=1),
    database_session: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> SellerTrustResponse:
    """Return seller trust indicators or explain why seller evidence is unavailable."""
    from app.repositories.review_repository import ReviewRepository

    repository = ReviewRepository()
    if repository.get_product(database_session, product_id) is None:
        raise HTTPException(status_code=404, detail="Product not found")
    if not repository.listing_belongs_to_product(database_session, listing_id=listing_id, product_id=product_id):
        raise HTTPException(status_code=404, detail="Listing not found for this product")
    listing = database_session.get(ProductListing, listing_id)
    assert listing is not None
    if listing.seller_id is None:
        return seller_trust_service.unavailable(None, "Seller identity is not available for this marketplace listing.")
    return seller_trust_service.result(database_session, listing.seller_id)
