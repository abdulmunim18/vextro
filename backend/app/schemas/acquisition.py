"""Pydantic schemas for marketplace acquisition ingestion."""

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    field_validator,
)


PlatformCode = Literal[
    "daraz",
    "priceoye",
]

IngestionStatus = Literal[
    "created",
    "updated",
    "duplicate",
]


class AcquisitionSellerInput(BaseModel):
    """Seller data collected from a marketplace."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    external_seller_id: str | None = Field(
        default=None,
        max_length=150,
    )

    name: str = Field(
        min_length=1,
        max_length=255,
    )

    profile_url: HttpUrl | None = None

    rating: Decimal | None = Field(
        default=None,
        ge=0,
        le=5,
    )

    review_count: int = Field(
        default=0,
        ge=0,
    )

    is_verified: bool = False


class AcquisitionListingInput(BaseModel):
    """Normalized listing received from the scraper."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    platform_code: PlatformCode

    product_variant_id: int = Field(
        ge=1,
    )

    external_id: str = Field(
        min_length=1,
        max_length=150,
    )

    title: str = Field(
        min_length=1,
        max_length=500,
    )

    product_url: HttpUrl

    current_price: Decimal = Field(
        ge=0,
    )

    original_price: Decimal | None = Field(
        default=None,
        ge=0,
    )

    currency: str = Field(
        default="PKR",
        min_length=3,
        max_length=3,
    )

    rating: Decimal | None = Field(
        default=None,
        ge=0,
        le=5,
    )

    review_count: int = Field(
        default=0,
        ge=0,
    )

    warranty: str | None = Field(
        default=None,
        max_length=255,
    )

    is_available: bool

    scraped_at: datetime

    seller: AcquisitionSellerInput | None = None

    raw_payload: dict[str, Any] = Field(
        default_factory=dict,
    )

    @field_validator("currency")
    @classmethod
    def normalize_currency(
        cls,
        value: str,
    ) -> str:
        """Convert currency to a three-letter uppercase code."""

        normalized_value = value.upper()

        if not normalized_value.isalpha():
            raise ValueError(
                "Currency must contain exactly three letters.",
            )

        return normalized_value

    @field_validator("scraped_at")
    @classmethod
    def require_timezone(
        cls,
        value: datetime,
    ) -> datetime:
        """Require timezone information in scraper timestamps."""

        if value.tzinfo is None:
            raise ValueError(
                "scraped_at must include timezone information.",
            )

        return value


class AcquisitionListingResponse(BaseModel):
    """Result returned after processing a listing capture."""

    model_config = ConfigDict(
        extra="forbid",
    )

    status: IngestionStatus

    platform_code: PlatformCode

    listing_id: int = Field(
        ge=1,
    )

    seller_id: int | None = Field(
        default=None,
        ge=1,
    )

    price_history_id: int | None = Field(
        default=None,
        ge=1,
    )

    listing_created: bool

    seller_created: bool

    price_history_created: bool

    alerts_triggered: int = Field(
        default=0,
        ge=0,
    )

    captured_at: datetime