"""Versioned seller-level estimate derived from review evidence."""

from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Identity, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class SellerTrustAnalysis(Base):
    __tablename__ = "seller_trust_analyses"
    __table_args__ = (
        UniqueConstraint("seller_id", "analysis_version", name="uq_seller_trust_analyses_seller_version"),
        CheckConstraint("(trust_level = 'insufficient_data' AND trust_score IS NULL) OR (trust_level IN ('low', 'moderate', 'high') AND trust_score BETWEEN 0 AND 100)", name="ck_seller_trust_score_level"),
        CheckConstraint("confidence_score BETWEEN 0 AND 100", name="ck_seller_trust_confidence_range"),
        CheckConstraint("confidence_level IN ('low', 'medium', 'high')", name="ck_seller_trust_confidence_level"),
        CheckConstraint("total_listings >= 0 AND total_reviews >= 0 AND analyzed_reviews >= 0 AND analyzed_reviews <= total_reviews", name="ck_seller_trust_counts"),
        CheckConstraint("analysis_coverage_percentage BETWEEN 0 AND 100", name="ck_seller_trust_coverage_range"),
        CheckConstraint("high_suspicion_percentage BETWEEN 0 AND 100", name="ck_seller_trust_high_rate_range"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    seller_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("sellers.id", ondelete="CASCADE"), nullable=False, index=True)
    analysis_version: Mapped[str] = mapped_column(String(50), nullable=False)
    trust_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    trust_level: Mapped[str] = mapped_column(String(20), nullable=False)
    confidence_score: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence_level: Mapped[str] = mapped_column(String(10), nullable=False)
    total_listings: Mapped[int] = mapped_column(Integer, nullable=False)
    total_reviews: Mapped[int] = mapped_column(Integer, nullable=False)
    analyzed_reviews: Mapped[int] = mapped_column(Integer, nullable=False)
    high_suspicion_review_count: Mapped[int] = mapped_column(Integer, nullable=False)
    medium_suspicion_review_count: Mapped[int] = mapped_column(Integer, nullable=False)
    low_suspicion_review_count: Mapped[int] = mapped_column(Integer, nullable=False)
    analysis_coverage_percentage: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    high_suspicion_percentage: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    average_review_suspicion_score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    verified_purchase_ratio: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    rating_average: Mapped[float | None] = mapped_column(Numeric(3, 2), nullable=True)
    rating_variance: Mapped[float | None] = mapped_column(Numeric(5, 3), nullable=True)
    signals: Mapped[dict] = mapped_column(JSONB, nullable=False)
    reasons: Mapped[list] = mapped_column(JSONB, nullable=False)
    analyzed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    seller = relationship("Seller")
