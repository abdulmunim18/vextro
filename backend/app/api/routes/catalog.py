from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.catalog import (
    BrandListResponse,
    CategoryListResponse,
    PlatformListResponse,
)
from app.services.catalog_service import (
    get_brands,
    get_categories,
    get_platforms,
)


router = APIRouter(
    prefix="/api/v1",
    tags=["Catalog"],
)


@router.get(
    "/categories",
    response_model=CategoryListResponse,
    status_code=status.HTTP_200_OK,
)
def list_categories(
    database_session: Session = Depends(get_db),
) -> CategoryListResponse:
    """Return active product categories."""

    categories = get_categories(
        database_session
    )

    return CategoryListResponse(
        items=list(categories)
    )


@router.get(
    "/brands",
    response_model=BrandListResponse,
    status_code=status.HTTP_200_OK,
)
def list_brands(
    database_session: Session = Depends(get_db),
) -> BrandListResponse:
    """Return active product brands."""

    brands = get_brands(
        database_session
    )

    return BrandListResponse(
        items=list(brands)
    )


@router.get(
    "/platforms",
    response_model=PlatformListResponse,
    status_code=status.HTTP_200_OK,
)
def list_platforms(
    database_session: Session = Depends(get_db),
) -> PlatformListResponse:
    """Return marketplaces supported by VEXTRO."""

    platforms = get_platforms(
        database_session
    )

    return PlatformListResponse(
        items=list(platforms)
    )