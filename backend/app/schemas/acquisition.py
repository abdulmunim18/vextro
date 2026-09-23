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

MAX_BULK_INGESTION_ITEMS = 100


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
        gt=0,
    )

    original_price: Decimal | None = Field(
        default=None,
        gt=0,
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

    competitor_alerts_triggered: int = Field(
        default=0,
        ge=0,
    )

    captured_at: datetime


class AcquisitionBulkInput(BaseModel):
    """Bounded raw items validated independently for partial success."""

    model_config = ConfigDict(extra="forbid")

    items: list[dict[str, Any]] = Field(
        min_length=1,
        max_length=MAX_BULK_INGESTION_ITEMS,
    )


BulkItemStatus = Literal[
    "created",
    "updated",
    "duplicate",
    "rejected",
    "failed",
]


class AcquisitionBulkItemResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    index: int = Field(ge=0)
    status: BulkItemStatus
    platform_code: PlatformCode | None = None
    external_id: str | None = None
    listing_id: int | None = Field(default=None, ge=1)
    price_history_id: int | None = Field(default=None, ge=1)
    price_history_created: bool = False
    alerts_triggered: int = Field(default=0, ge=0)
    competitor_alerts_triggered: int = Field(default=0, ge=0)
    error_code: str | None = None
    error_stage: Literal["validation", "ingestion"] | None = None
    message: str | None = None


class AcquisitionBulkResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    received: int = Field(ge=1, le=MAX_BULK_INGESTION_ITEMS)
    succeeded: int = Field(ge=0)
    duplicates: int = Field(ge=0)
    rejected: int = Field(ge=0)
    failed: int = Field(ge=0)
    results: list[AcquisitionBulkItemResponse]
