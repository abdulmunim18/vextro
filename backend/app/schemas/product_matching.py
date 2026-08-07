"""Schemas for marketplace product-to-variant matching."""

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)


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

    product_variant_id: int | None = Field(
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