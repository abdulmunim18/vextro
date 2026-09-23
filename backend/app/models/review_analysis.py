"""Versioned, explainable suspicion evidence for persisted reviews."""

from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Identity, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ReviewAnalysis(Base):
    __tablename__ = "review_analyses"
    __table_args__ = (
        UniqueConstraint("raw_review_id", "analysis_version", name="uq_review_analyses_review_version"),
        CheckConstraint("suspicion_score BETWEEN 0 AND 100", name="ck_review_analyses_score_range"),
        CheckConstraint("suspicion_level IN ('low', 'medium', 'high')", name="ck_review_analyses_level"),
        CheckConstraint("duplicate_similarity_score BETWEEN 0 AND 100", name="ck_review_analyses_similarity_range"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    raw_review_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("raw_reviews.id", ondelete="CASCADE"), nullable=False, index=True)
    analysis_version: Mapped[str] = mapped_column(String(50), nullable=False)
    suspicion_score: Mapped[int] = mapped_column(Integer, nullable=False)
    suspicion_level: Mapped[str] = mapped_column(String(10), nullable=False)
    duplicate_similarity_score: Mapped[int] = mapped_column(Integer, nullable=False)
    text_anomaly_score: Mapped[int] = mapped_column(Integer, nullable=False)
    rating_anomaly_score: Mapped[int] = mapped_column(Integer, nullable=False)
    temporal_anomaly_score: Mapped[int] = mapped_column(Integer, nullable=False)
    reviewer_anomaly_score: Mapped[int] = mapped_column(Integer, nullable=False)
    is_exact_duplicate: Mapped[bool] = mapped_column(nullable=False)
    is_near_duplicate: Mapped[bool] = mapped_column(nullable=False)
    signals: Mapped[dict] = mapped_column(JSONB, nullable=False)
    reasons: Mapped[list] = mapped_column(JSONB, nullable=False)
    analyzed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    raw_review = relationship("RawReview")
