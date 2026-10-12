"""What the public says about a phone on a guide site, outside any shop.

Kept apart from marketplace reviews on purpose. A review belongs to a
listing and a buyer and carries a star rating; a community opinion belongs
to the phone itself, can be posted by anyone and has no rating of its own.
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ProductCommunityRating(Base):
    """One source's overall rating of a phone, and the price it lists."""

    __tablename__ = "product_community_ratings"
    __table_args__ = (
        UniqueConstraint(
            "canonical_product_id",
            "source",
            name="uq_product_community_ratings_product_source",
        ),
        CheckConstraint(
            "rating IS NULL OR rating BETWEEN 0 AND 5",
            name="ck_product_community_ratings_rating_range",
        ),
        CheckConstraint(
            "rating_count >= 0",
            name="ck_product_community_ratings_count_non_negative",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    canonical_product_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("canonical_products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source: Mapped[str] = mapped_column(String(40), nullable=False)
    source_product_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    opinions_url: Mapped[str | None] = mapped_column(Text)
    rating: Mapped[Decimal | None] = mapped_column(Numeric(3, 2))
    rating_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # The manufacturer's listed retail price as the source states it: a
    # reference figure, never an offer anyone can buy at.
    reference_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
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


class CommunityOpinion(Base):
    """One visitor's opinion of a phone, as a guide site published it."""

    __tablename__ = "community_opinions"
    __table_args__ = (
        UniqueConstraint(
            "source",
            "opinion_fingerprint",
            name="uq_community_opinions_source_fingerprint",
        ),
        CheckConstraint(
            "suspicion_score IS NULL OR suspicion_score BETWEEN 0 AND 100",
            name="ck_community_opinions_score_range",
        ),
        CheckConstraint(
            "suspicion_level IS NULL OR "
            "suspicion_level IN ('low', 'medium', 'high')",
            name="ck_community_opinions_level",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    canonical_product_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("canonical_products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source: Mapped[str] = mapped_column(String(40), nullable=False)
    # Identifies the opinion across crawls so it is stored once.
    opinion_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    author_display_name: Mapped[str | None] = mapped_column(String(120))
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    opinion_text: Mapped[str] = mapped_column(Text, nullable=False)
    # True when the scraper removed a phone number from the text.
    contact_removed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    source_position: Mapped[int | None] = mapped_column(Integer)

    # Filled by the opinion risk scorer; empty until an opinion is scored.
    analysis_version: Mapped[str | None] = mapped_column(String(50))
    suspicion_score: Mapped[int | None] = mapped_column(Integer)
    suspicion_level: Mapped[str | None] = mapped_column(String(10))
    opinion_kind: Mapped[str | None] = mapped_column(String(20))
    analysis_reasons: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
