from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


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


class PriceAlertCreate(BaseModel):
    """Request for creating a product or listing price alert."""

    canonical_product_id: int | None = Field(
        default=None,
        ge=1,
    )

    listing_id: int | None = Field(
        default=None,
        ge=1,
    )

    target_price: Decimal = Field(
        gt=0,
        max_digits=14,
        decimal_places=2,
    )

    currency: str = Field(
        default="PKR",
        min_length=3,
        max_length=3,
    )

    @field_validator("currency")
    @classmethod
    def normalize_currency(
        cls,
        value: str,
    ) -> str:
        """Normalize and validate the currency code."""

        normalized_currency = value.strip().upper()

        if (
            len(normalized_currency) != 3
            or not normalized_currency.isalpha()
        ):
            raise ValueError(
                "currency must contain exactly three letters"
            )

        return normalized_currency

    @model_validator(mode="after")
    def validate_exactly_one_target(self) -> Self:
        """Require either a product or listing target, never both."""

        has_product_target = self.canonical_product_id is not None
        has_listing_target = self.listing_id is not None

        if has_product_target == has_listing_target:
            raise ValueError(
                "Exactly one of canonical_product_id "
                "or listing_id must be provided"
            )

        return self


class PriceAlertUpdate(BaseModel):
    """Fields that may be changed on an existing alert."""

    target_price: Decimal | None = Field(
        default=None,
        gt=0,
        max_digits=14,
        decimal_places=2,
    )

    currency: str | None = Field(
        default=None,
        min_length=3,
        max_length=3,
    )

    is_active: bool | None = None

    @field_validator("currency")
    @classmethod
    def normalize_optional_currency(
        cls,
        value: str | None,
    ) -> str | None:
        """Normalize an optional currency code."""

        if value is None:
            return None

        normalized_currency = value.strip().upper()

        if (
            len(normalized_currency) != 3
            or not normalized_currency.isalpha()
        ):
            raise ValueError(
                "currency must contain exactly three letters"
            )

        return normalized_currency

    @model_validator(mode="after")
    def require_at_least_one_update(self) -> Self:
        """Reject an empty PATCH request."""

        if (
            self.target_price is None
            and self.currency is None
            and self.is_active is None
        ):
            raise ValueError(
                "At least one field must be provided"
            )

        return self


class PriceAlertResponse(ORMResponse):
    """Authenticated consumer price-alert response."""

    id: int
    user_id: int

    canonical_product_id: int | None
    listing_id: int | None

    target_price: Decimal
    currency: str

    is_active: bool
    is_triggered: bool
    notification_count: int

    last_checked_at: datetime | None
    triggered_at: datetime | None
    last_notified_at: datetime | None

    created_at: datetime
    updated_at: datetime


class PriceAlertListResponse(BaseModel):
    """Alerts belonging to the authenticated consumer."""

    total: int = Field(ge=0)

    items: list[PriceAlertResponse] = Field(
        default_factory=list,
    )