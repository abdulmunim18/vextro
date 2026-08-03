from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ORMResponse(BaseModel):
    """Base response schema supporting SQLAlchemy objects."""

    model_config = ConfigDict(from_attributes=True)


class PriceHistoryPointResponse(ORMResponse):
    """One historical price snapshot for a marketplace listing."""

    id: int
    listing_id: int
    price: Decimal
    original_price: Decimal | None
    currency: str
    is_available: bool
    source: str
    captured_at: datetime


class PriceSummaryResponse(BaseModel):
    """Calculated price statistics for one marketplace listing."""

    current_price: Decimal | None = None
    lowest_price: Decimal | None = None
    highest_price: Decimal | None = None
    average_price: Decimal | None = None
    price_change: Decimal | None = None
    price_change_percentage: Decimal | None = None
    first_captured_at: datetime | None = None
    last_captured_at: datetime | None = None


class ListingPriceHistoryResponse(BaseModel):
    """Historical pricing information for one marketplace listing."""

    listing_id: int
    platform_id: int
    seller_id: int | None

    listing_title: str
    product_url: str
    currency: str

    platform_name: str | None = None
    seller_name: str | None = None

    summary: PriceSummaryResponse

    points: list[PriceHistoryPointResponse] = Field(
        default_factory=list,
    )


class ProductPriceHistoryResponse(BaseModel):
    """Complete historical pricing response for a canonical product."""

    product_id: int
    product_name: str

    date_from: datetime | None = None
    date_to: datetime | None = None

    total_listings: int = Field(ge=0)
    total_points: int = Field(ge=0)

    listings: list[ListingPriceHistoryResponse] = Field(
        default_factory=list,
    )