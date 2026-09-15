"""Authenticated API contracts for suspicious-review evidence."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class ReviewAnalysisResponse(BaseModel):
    review_id: int
    listing_id: int
    analysis_version: str
    suspicion_score: int = Field(ge=0, le=100)
    suspicion_level: Literal["low", "medium", "high"]
    duplicate_similarity_score: int = Field(ge=0, le=100)
    text_anomaly_score: int
    rating_anomaly_score: int
    temporal_anomaly_score: int
    reviewer_anomaly_score: int
    is_exact_duplicate: bool
    is_near_duplicate: bool
    signals: dict[str, Any]
    reasons: list[str]
    analyzed_at: datetime


class ProductReviewAnalysisResponse(BaseModel):
    product_id: int
    listing_id: int | None
    analysis_version: str
    total_reviews: int
    analyzed_reviews: int
    low: int
    medium: int
    high: int
    high_suspicion_percentage: float
    average_suspicion_score: float | None
    exact_duplicate_count: int
    near_duplicate_count: int
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    total_pages: int
    reviews: list[ReviewAnalysisResponse]
