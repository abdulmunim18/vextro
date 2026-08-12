from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ORMResponse(BaseModel):
    """Base schema that supports SQLAlchemy model conversion."""

    model_config = ConfigDict(from_attributes=True)


class CategoryResponse(ORMResponse):
    """Public category response."""

    id: int
    name: str
    slug: str


class BrandResponse(ORMResponse):
    """Public brand response."""

    id: int
    name: str
    slug: str


class PlatformResponse(ORMResponse):
    """Supported marketplace platform response."""

    id: int
    name: str
    code: str
    base_url: str


class ProductImageResponse(ORMResponse):
    """Product or marketplace listing image response."""

    id: int
    canonical_product_id: int | None
    listing_id: int | None
    image_url: str
    alt_text: str | None
    is_primary: bool
    sort_order: int
    created_at: datetime


class ProductVariantResponse(ORMResponse):
    """Specific configuration of a canonical product."""

    id: int
    canonical_product_id: int
    sku: str | None
    ram_gb: int | None
    storage_gb: int | None
    color: str | None
    condition: str
    variant_attributes: dict[str, Any] = Field(default_factory=dict)
    is_active: bool
    created_at: datetime
    updated_at: datetime


class SellerResponse(ORMResponse):
    """Marketplace seller response."""

    id: int
    platform_id: int
    external_seller_id: str | None
    name: str
    profile_url: str | None
    rating: Decimal | None
    review_count: int
    is_verified: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ProductListingResponse(ORMResponse):
    """Marketplace-specific product listing response."""

    id: int
    platform_id: int
    product_variant_id: int
    seller_id: int | None
    external_id: str
    title: str
    product_url: str
    current_price: Decimal
    original_price: Decimal | None
    currency: str
    rating: Decimal | None
    review_count: int
    warranty: str | None
    is_available: bool
    first_seen_at: datetime
    last_seen_at: datetime

    seller: SellerResponse | None = None
    images: list[ProductImageResponse] = Field(default_factory=list)


class ProductListItemResponse(ORMResponse):
    """Compact product response used in search results."""

    id: int
    category_id: int
    brand_id: int | None
    name: str
    slug: str
    model: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    lowest_price: Decimal | None = None
    highest_rating: Decimal | None = None
    available_listing_count: int = Field(default=0, ge=0)
    platform_codes: list[str] = Field(default_factory=list)


class ProductDetailResponse(ProductListItemResponse):
    """Detailed canonical product response."""

    description: str | None
    specifications: dict[str, Any] = Field(default_factory=dict)
    variants: list[ProductVariantResponse] = Field(default_factory=list)
    images: list[ProductImageResponse] = Field(default_factory=list)


class ProductListingsResponse(ORMResponse):
    """Listings associated with one canonical product."""

    product_id: int
    product_name: str
    total: int
    items: list[ProductListingResponse] = Field(default_factory=list)


class ProductListResponse(BaseModel):
    """Paginated product search response."""

    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    total_pages: int = Field(ge=0)
    items: list[ProductListItemResponse] = Field(default_factory=list)
