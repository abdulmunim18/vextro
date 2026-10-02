"""Schemas for marketplace product-to-variant matching."""

from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)

from app.schemas.acquisition import PlatformCode


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

    # Set by scrapers whose source publishes clean, structured product
    # data (brand, model, colour and storage as separate fields). It
    # lets the matcher add a missing variant or a brand-new product to
    # the catalog instead of parking the item for manual review.
    allow_catalog_create: bool = False

    specifications: dict[str, Any] = Field(
        default_factory=dict,
    )

    @field_validator("specifications")
    @classmethod
    def bound_specifications(
        cls,
        value: dict[str, Any],
    ) -> dict[str, str]:
        """Keep a compact set of display-safe label/value pairs."""

        bounded: dict[str, str] = {}
        for raw_key, raw_value in list(value.items())[:80]:
            key = str(raw_key).strip()[:80]
            if not key or raw_value is None:
                continue
            text = str(raw_value).strip()
            if text:
                bounded[key] = text[:2000]
        return bounded


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
