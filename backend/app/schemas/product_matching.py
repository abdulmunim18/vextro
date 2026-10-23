"""Schemas for marketplace product-to-variant matching."""

from decimal import Decimal
from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)

from app.schemas.acquisition import PlatformCode


MatchTier = Literal["EXACT", "HIGH", "MEDIUM", "LOW"]


class ProductMatchRequest(BaseModel):
    """Normalized product information received for matching."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    title: str = Field(
        min_length=2,
        max_length=500,
    )

    platform_code: PlatformCode | None = None

    external_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=150,
    )

    brand: str | None = Field(
        default=None,
        max_length=120,
    )

    model: str | None = Field(
        default=None,
        max_length=150,
    )

    ram_gb: int | None = Field(
        default=None,
        ge=1,
        le=128,
    )

    storage_gb: int | None = Field(
        default=None,
        ge=1,
        le=8192,
    )

    color: str | None = Field(
        default=None,
        max_length=120,
    )

    sku: str | None = Field(
        default=None,
        max_length=120,
    )

    # Daraz sellers prefix their store name onto the listing title. Knowing
    # the store lets the matcher strip it before comparing the phone.
    seller_name: str | None = Field(
        default=None,
        max_length=255,
    )

    specifications: dict[str, Any] = Field(
        default_factory=dict,
    )

    # Set by a source whose title is the marketplace's own model name
    # rather than a seller's free text. Only then does "5G" in the title,
    # or its absence, say which of two phones is meant.
    exact_model_title: bool = False

    @field_validator("specifications")
    @classmethod
    def bound_specifications(
        cls,
        value: dict[str, Any],
    ) -> dict[str, Any]:
        """Keep normalized specification payloads deliberately small."""

        if len(value) > 60:
            raise ValueError(
                "specifications must contain at most 60 fields"
            )

        return value

    # The catalogue category the listing belongs to. Matching looks only
    # at products of that category and new products are filed under it.
    # Absent means a smartphone, as every listing was before categories.
    category_slug: str | None = Field(default=None, max_length=120)

    @field_validator("category_slug")
    @classmethod
    def category_is_known(cls, value: str | None) -> str | None:
        return _known_category(value)


def _known_category(value: str | None) -> str | None:
    """Accept only a category VEXTRO has a profile for; None is a phone."""

    if value is None or not value.strip():
        return None

    from app.services.category_profiles import profile_for

    return profile_for(value).slug


class ProductResolveRequest(ProductMatchRequest):
    """A match request that may also create missing catalog records."""

    allow_create: bool = True
    # False files the listing only under a product the catalogue already
    # holds. A seller marketplace (Daraz) uses it in categories where its
    # titles are mostly unbranded: it may add a colour to a known tablet,
    # but never a new tablet or brand.
    allow_new_product: bool = True
    # The listing's own price, sent with match-only listings. A seller's
    # "Galaxy Watch Ultra" at a tenth of what the stores ask is a copy
    # wearing the name, not an offer for the watch.
    listing_price: Decimal | None = Field(default=None, gt=0)


class ProductMatchResponse(BaseModel):
    """Best VEXTRO product variant match."""

    model_config = ConfigDict(
        extra="forbid",
    )

    matched: bool

    confidence: int = Field(
        ge=0,
        le=100,
    )

    match_tier: MatchTier = "LOW"

    product_variant_id: int | None = Field(
        default=None,
        ge=1,
    )

    suggested_product_variant_id: int | None = Field(
        default=None,
        ge=1,
    )

    canonical_product_id: int | None = Field(
        default=None,
        ge=1,
    )

    product_name: str | None = None
    brand_name: str | None = None
    model: str | None = None

    ram_gb: int | None = Field(
        default=None,
        ge=1,
    )

    storage_gb: int | None = Field(
        default=None,
        ge=1,
    )

    color: str | None = None

    reason: str


class ProductResolveResponse(ProductMatchResponse):
    """A match response that reports any catalog records it created."""

    product_created: bool = False
    variant_created: bool = False
