from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.platform import Platform
    from app.models.product_listing import ProductListing
    from app.models.seller import Seller


class RawReview(Base):
    """Normalized marketplace review evidence, without analysis labels."""

    __tablename__ = "raw_reviews"

    __table_args__ = (
        UniqueConstraint(
            "platform_id",
            "external_review_id",
            name="uq_raw_reviews_platform_external_id",
        ),
        UniqueConstraint(
            "platform_id",
            "review_fingerprint",
            name="uq_raw_reviews_platform_fingerprint",
        ),
        CheckConstraint(
            "rating >= 1 AND rating <= 5",
            name="ck_raw_reviews_rating_range",
        ),
        CheckConstraint(
            "helpful_count IS NULL OR helpful_count >= 0",
            name="ck_raw_reviews_helpful_count_non_negative",
        ),
        CheckConstraint(
            "char_length(review_fingerprint) = 64",
            name="ck_raw_reviews_fingerprint_sha256_length",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(),
        primary_key=True,
    )
    platform_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("platforms.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    product_listing_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("product_listings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    seller_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("sellers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    external_review_id: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
    )
    review_fingerprint: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    reviewer_external_id: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
    )
    reviewer_display_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    rating: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    review_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    verified_purchase: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
    )
    helpful_count: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    source_url: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    raw_metadata: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    platform: Mapped["Platform"] = relationship()
    product_listing: Mapped["ProductListing"] = relationship(
        back_populates="reviews",
    )
    seller: Mapped["Seller | None"] = relationship(
        back_populates="reviews",
    )
