"""Validation and response contracts for marketplace review data."""

from datetime import date, datetime
import json
import re
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    StrictBool,
    field_validator,
)

from app.services.review_normalization import (
    normalize_optional_identifier,
    normalize_review_text,
    normalize_reviewed_at,
)


PlatformCode = Literal["daraz", "priceoye"]
StrictRating = Annotated[int, Field(strict=True, ge=1, le=5)]
StrictHelpfulCount = Annotated[int, Field(strict=True, ge=0)]


class ReviewInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    external_review_id: str | None = Field(default=None, max_length=150)
    reviewer_external_id: str | None = Field(default=None, max_length=150)
    reviewer_display_name: str | None = Field(default=None, max_length=255)
    rating: StrictRating
    review_text: str | None = Field(default=None, max_length=10_000)
    reviewed_at: datetime | date | None = None
    verified_purchase: StrictBool | None = None
    helpful_count: StrictHelpfulCount | None = None
    raw_metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "external_review_id",
        "reviewer_external_id",
        "reviewer_display_name",
        mode="before",
    )
    @classmethod
    def normalize_identifiers(cls, value: object) -> object:
        if value is not None and not isinstance(value, str):
            raise ValueError("identifier values must be strings")
        return normalize_optional_identifier(value)

    @field_validator("review_text", mode="before")
    @classmethod
    def normalize_text(cls, value: object) -> object:
        if value is not None and not isinstance(value, str):
            raise ValueError("review_text must be a string")
        return normalize_review_text(value)

    @field_validator("reviewed_at")
    @classmethod
    def normalize_date(
        cls,
        value: datetime | date | None,
    ) -> datetime | None:
        return normalize_reviewed_at(value)

    @field_validator("reviewed_at", mode="before")
    @classmethod
    def preserve_date_only_precision(cls, value: object) -> object:
        if isinstance(value, str) and re.fullmatch(
            r"\d{4}-\d{2}-\d{2}",
            value.strip(),
        ):
            return date.fromisoformat(value.strip())
        return value

    @field_validator("raw_metadata")
    @classmethod
    def bound_metadata(cls, value: dict[str, Any]) -> dict[str, Any]:
        if len(value) > 30:
            raise ValueError("raw_metadata must contain at most 30 fields")
        try:
            serialized = json.dumps(value, ensure_ascii=False, default=str)
        except (TypeError, ValueError) as exc:
            raise ValueError("raw_metadata must be JSON serializable") from exc
        if len(serialized) > 8_000:
            raise ValueError("raw_metadata must not exceed 8000 characters")
        return value


class ReviewBatchInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    platform_code: PlatformCode
    external_listing_id: str = Field(min_length=1, max_length=150)
    source_url: HttpUrl
    reviews: list[ReviewInput] = Field(min_length=1, max_length=100)


class ReviewIngestionItemResponse(BaseModel):
    id: int = Field(ge=1)
    status: Literal["created", "duplicate"]
    external_review_id: str | None
    review_fingerprint: str = Field(min_length=64, max_length=64)


class ReviewBatchResponse(BaseModel):
    platform_code: PlatformCode
    listing_id: int = Field(ge=1)
    seller_id: int | None = Field(default=None, ge=1)
    created_count: int = Field(ge=0)
    duplicate_count: int = Field(ge=0)
    items: list[ReviewIngestionItemResponse]


class ReviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    platform_code: PlatformCode
    product_listing_id: int
    seller_id: int | None
    external_review_id: str | None
    review_fingerprint: str
    reviewer_external_id: str | None
    reviewer_display_name: str | None
    rating: int
    review_text: str | None
    reviewed_at: datetime | None
    verified_purchase: bool | None
    helpful_count: int | None
    source_url: str
    raw_metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class ProductReviewsResponse(BaseModel):
    product_id: int
    listing_id: int | None
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    total_pages: int = Field(ge=0)
    average_rating: float | None
    rating_distribution: dict[int, int]
    items: list[ReviewResponse]
