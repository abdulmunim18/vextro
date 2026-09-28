from fastapi import (
    APIRouter,
    Depends,
    Path,
    Query,
    Response,
    status,
)
from sqlalchemy.orm import Session

from app.api.dependencies.roles import admin_only
from app.core.database import get_db
from app.models.user import User
from app.schemas.admin_catalog import (
    AdminProductListResponse,
    AdminProductResponse,
    AdminProductStatusUpdate,
    AdminListingListResponse,
)
from app.schemas.acquisition import PlatformCode
from app.schemas.pending_product_match import (
    PendingMatchStatus,
    PendingProductMatchListResponse,
    PendingProductMatchReplayResponse,
    PendingProductMatchResolve,
    PendingProductMatchResponse,
    ProductVariantOptionListResponse,
)
from app.services.admin_catalog_service import (
    AdminCatalogService,
)
from app.services.pending_product_match_service import PendingProductMatchService


router = APIRouter(
    prefix="/api/v1/admin",
    tags=["admin-catalog"],
)
pending_product_match_service = PendingProductMatchService()


@router.get(
    "/products",
    response_model=AdminProductListResponse,
    summary="List Admin Products",
    description=(
        "Search and filter canonical products "
        "for administrator catalog management."
    ),
)
def read_admin_products(
    q: str | None = Query(
        default=None,
        min_length=1,
        max_length=120,
        description=(
            "Search by product, model, brand "
            "or category."
        ),
    ),
    category_id: int | None = Query(
        default=None,
        ge=1,
        description="Filter by category ID.",
    ),
    brand_id: int | None = Query(
        default=None,
        ge=1,
        description="Filter by brand ID.",
    ),
    is_active: bool | None = Query(
        default=None,
        description=(
            "Filter active or inactive products."
        ),
    ),
    page: int = Query(
        default=1,
        ge=1,
        description="Results page number.",
    ),
    page_size: int = Query(
        default=20,
        ge=1,
        le=100,
        description="Products returned per page.",
    ),
    database_session: Session = Depends(get_db),
    current_admin: User = Depends(admin_only),
) -> AdminProductListResponse:
    del current_admin

    return AdminCatalogService.list_products(
        database_session,
        query=q,
        category_id=category_id,
        brand_id=brand_id,
        is_active=is_active,
        page=page,
        page_size=page_size,
    )


@router.patch(
    "/products/{product_id}/status",
    response_model=AdminProductResponse,
    summary="Update Admin Product Status",
    description=(
        "Activate or deactivate one canonical "
        "VEXTRO product."
    ),
)
def update_admin_product_status(
    payload: AdminProductStatusUpdate,
    product_id: int = Path(
        ge=1,
        description="Canonical product ID.",
    ),
    database_session: Session = Depends(get_db),
    current_admin: User = Depends(admin_only),
) -> AdminProductResponse:
    del current_admin

    return AdminCatalogService.update_product_status(
        database_session,
        product_id=product_id,
        payload=payload,
    )
@router.get(
    "/listings",
    response_model=AdminListingListResponse,
    summary="List Admin Marketplace Listings",
    description=(
        "Monitor Daraz and PriceOye marketplace "
        "listings, sellers, prices and availability."
    ),
)
def read_admin_listings(
    q: str | None = Query(
        default=None,
        min_length=1,
        max_length=150,
        description=(
            "Search by listing title, external ID, "
            "product, model or seller."
        ),
    ),
    platform_id: int | None = Query(
        default=None,
        ge=1,
        description="Filter by marketplace platform ID.",
    ),
    product_id: int | None = Query(
        default=None,
        ge=1,
        description="Filter by canonical product ID.",
    ),
    is_available: bool | None = Query(
        default=None,
        description=(
            "Filter available or unavailable listings."
        ),
    ),
    page: int = Query(
        default=1,
        ge=1,
        description="Results page number.",
    ),
    page_size: int = Query(
        default=20,
        ge=1,
        le=100,
        description="Listings returned per page.",
    ),
    database_session: Session = Depends(get_db),
    current_admin: User = Depends(admin_only),
) -> AdminListingListResponse:
    del current_admin

    return AdminCatalogService.list_listings(
        database_session,
        query=q,
        platform_id=platform_id,
        product_id=product_id,
        is_available=is_available,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/pending-product-matches",
    response_model=PendingProductMatchListResponse,
)
def read_pending_product_matches(
    q: str | None = Query(default=None, min_length=1, max_length=150),
    platform_code: PlatformCode | None = Query(default=None),
    match_status: PendingMatchStatus | None = Query(default="pending", alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    database_session: Session = Depends(get_db),
    current_admin: User = Depends(admin_only),
) -> PendingProductMatchListResponse:
    del current_admin
    return pending_product_match_service.list(
        database_session,
        query=q,
        platform_code=platform_code,
        match_status=match_status,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/product-variant-options",
    response_model=ProductVariantOptionListResponse,
)
def read_product_variant_options(
    q: str = Query(min_length=2, max_length=150),
    limit: int = Query(default=20, ge=1, le=50),
    database_session: Session = Depends(get_db),
    current_admin: User = Depends(admin_only),
) -> ProductVariantOptionListResponse:
    del current_admin
    return pending_product_match_service.variant_options(
        database_session,
        query=q,
        limit=limit,
    )


@router.patch(
    "/pending-product-matches/{match_id}/resolve",
    response_model=PendingProductMatchResponse,
)
def resolve_pending_product_match(
    payload: PendingProductMatchResolve,
    match_id: int = Path(ge=1),
    database_session: Session = Depends(get_db),
    current_admin: User = Depends(admin_only),
) -> PendingProductMatchResponse:
    return pending_product_match_service.resolve(
        database_session,
        match_id=match_id,
        user_id=current_admin.id,
        payload=payload,
    )


@router.post(
    "/pending-product-matches/{match_id}/replay",
    response_model=PendingProductMatchReplayResponse,
)
def replay_pending_product_match(
    match_id: int = Path(ge=1),
    database_session: Session = Depends(get_db),
    current_admin: User = Depends(admin_only),
) -> PendingProductMatchReplayResponse:
    del current_admin
    return pending_product_match_service.replay(
        database_session,
        match_id=match_id,
    )


@router.delete(
    "/pending-product-matches/{match_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_pending_product_match(
    match_id: int = Path(ge=1),
    database_session: Session = Depends(get_db),
    current_admin: User = Depends(admin_only),
) -> Response:
    """Permanently discard one unwanted marketplace match candidate."""

    del current_admin
    pending_product_match_service.delete(
        database_session,
        match_id=match_id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
