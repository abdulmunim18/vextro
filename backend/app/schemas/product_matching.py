"""Schemas for marketplace product-to-variant matching."""

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

    specifications: dict[str, Any] = Field(
        default_factory=dict,
    )

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


class ProductResolveRequest(ProductMatchRequest):
    """A match request that may also create missing catalog records."""

    allow_create: bool = True

    category_slug: str | None = Field(
        default=None,
        max_length=120,
    )


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
