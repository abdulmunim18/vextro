"""Authenticated seller trust-indicator API contracts."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class SellerTrustResponse(BaseModel):
    seller_id: int | None
    seller_name: str | None
    status: Literal["available", "insufficient_data"]
    analysis_version: str
    trust_score: int | None = Field(default=None, ge=0, le=100)
    trust_level: Literal["low", "moderate", "high", "insufficient_data"]
    confidence_score: int = Field(ge=0, le=100)
    confidence_level: Literal["low", "medium", "high"]
    total_listings: int
    total_reviews: int
    analyzed_reviews: int
    analysis_coverage_percentage: float
    high_suspicion_review_count: int
    medium_suspicion_review_count: int
    low_suspicion_review_count: int
    high_suspicion_percentage: float
    average_review_suspicion_score: float | None
    verified_purchase_ratio: float | None
    rating_average: float | None
    rating_variance: float | None
    signals: dict[str, Any]
    reasons: list[str]
    analyzed_at: datetime | None
