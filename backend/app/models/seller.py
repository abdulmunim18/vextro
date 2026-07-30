from __future__ import annotations

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
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Seller(Base):
    """A seller operating on a supported marketplace platform."""

    __tablename__ = "sellers"

    __table_args__ = (
        UniqueConstraint(
            "platform_id",
            "external_seller_id",
            name="uq_sellers_platform_external_id",
        ),
        CheckConstraint(
            "rating IS NULL OR (rating >= 0 AND rating <= 5)",
            name="ck_sellers_rating_range",
        ),
        CheckConstraint(
            "review_count >= 0",
            name="ck_sellers_review_count_non_negative",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(),
        primary_key=True,
    )

    platform_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "platforms.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    external_seller_id: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )

    profile_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    rating: Mapped[Decimal | None] = mapped_column(
        Numeric(3, 2),
        nullable=True,
    )

    review_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )

    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
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

    listings: Mapped[list["ProductListing"]] = relationship(
        back_populates="seller",
    )