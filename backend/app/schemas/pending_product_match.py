"""Schemas for unresolved marketplace-to-catalog mappings."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from app.schemas.acquisition import AcquisitionListingResponse, PlatformCode
from app.schemas.product_matching import ProductMatchRequest


PendingMatchStatus = Literal[
    "pending",
    "resolved",
    "replayed",
    "dismissed",
]


class PendingProductMatchCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    platform_code: PlatformCode
    external_id: str = Field(min_length=1, max_length=150)
    title: str = Field(min_length=1, max_length=500)
    product_url: HttpUrl
    match_payload: ProductMatchRequest
    listing_payload: dict[str, Any]
    match_confidence: int = Field(ge=0, le=100)
    match_reason: str = Field(min_length=1, max_length=500)
    suggested_product_variant_id: int | None = Field(default=None, ge=1)


class PendingProductMatchResolve(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_variant_id: int = Field(ge=1)


class PendingProductMatchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    platform_code: PlatformCode
    external_id: str
    title: str
    product_url: str
    match_payload: dict[str, Any]
    listing_payload: dict[str, Any]
    match_confidence: int
    match_reason: str
    suggested_product_variant_id: int | None
    assigned_product_variant_id: int | None
    assigned_product_name: str | None = None
    assigned_variant_label: str | None = None
    status: PendingMatchStatus
    resolved_by_user_id: int | None
    resolved_at: datetime | None
    replayed_at: datetime | None
    replay_result: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class PendingProductMatchListResponse(BaseModel):
    items: list[PendingProductMatchResponse]
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    total_items: int = Field(ge=0)
    total_pages: int = Field(ge=0)


class PendingProductMatchReplayResponse(BaseModel):
    pending_match: PendingProductMatchResponse
    ingestion: AcquisitionListingResponse


class ProductVariantOption(BaseModel):
    id: int
    canonical_product_id: int
    product_name: str
    brand_name: str | None
    model: str | None
    sku: str | None
    ram_gb: int | None
    storage_gb: int | None
    color: str | None


class ProductVariantOptionListResponse(BaseModel):
    items: list[ProductVariantOption]
