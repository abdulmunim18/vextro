from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Numeric,
    String,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.product_listing import ProductListing


class PriceHistory(Base):
    """A historical price snapshot captured for a marketplace listing."""

    __tablename__ = "price_history"

    __table_args__ = (
        CheckConstraint(
            "price >= 0",
            name="ck_price_history_price_non_negative",
        ),
        CheckConstraint(
            "original_price IS NULL OR original_price >= 0",
            name="ck_price_history_original_price_non_negative",
        ),
        CheckConstraint(
            "char_length(currency) = 3",
            name="ck_price_history_currency_length",
        ),
        Index(
            "ix_price_history_listing_captured_at",
            "listing_id",
            "captured_at",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(),
        primary_key=True,
    )

    listing_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "product_listings.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    price: Mapped[Decimal] = mapped_column(
        Numeric(14, 2),
        nullable=False,
    )

    original_price: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 2),
        nullable=True,
    )

    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        server_default=text("'PKR'"),
    )

    is_available: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
    )

    source: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        server_default=text("'scraper'"),
    )

    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    listing: Mapped["ProductListing"] = relationship(
        back_populates="price_history",
    )