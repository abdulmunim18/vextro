from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field


class AdminProductResponse(BaseModel):
    """Canonical product information for administrators."""

    id: int

    name: str
    slug: str
    model: str | None

    category_id: int
    category_name: str

    brand_id: int | None
    brand_name: str | None

    is_active: bool

    variant_count: int = Field(ge=0)
    listing_count: int = Field(ge=0)
    available_listing_count: int = Field(ge=0)

    created_at: datetime
    updated_at: datetime


class AdminProductListResponse(BaseModel):
    """Paginated administrator product response."""

    items: list[AdminProductResponse]

    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)

    total_items: int = Field(ge=0)
    total_pages: int = Field(ge=0)


class AdminProductStatusUpdate(BaseModel):
    """Activate or deactivate one canonical product."""

    is_active: bool
class AdminListingResponse(BaseModel):
    """Marketplace listing information for administrators."""

    id: int
    external_id: str

    title: str
    product_url: str

    platform_id: int
    platform_name: str
    platform_code: str

    product_id: int
    product_name: str
    product_model: str | None

    variant_id: int
    variant_sku: str | None
    ram_gb: int | None
    storage_gb: int | None
    color: str | None

    seller_id: int | None
    seller_name: str | None
    seller_is_verified: bool | None

    current_price: Decimal
    original_price: Decimal | None
    currency: str

    rating: Decimal | None
    review_count: int = Field(ge=0)
    warranty: str | None

    is_available: bool

    first_seen_at: datetime
    last_seen_at: datetime


class AdminListingListResponse(BaseModel):
    """Paginated marketplace-listing monitoring response."""

    items: list[AdminListingResponse]

    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)

    total_items: int = Field(ge=0)
    total_pages: int = Field(ge=0)