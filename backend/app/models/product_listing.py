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
    Integer,
    Numeric,
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
    from app.models.product_variant import ProductVariant
    from app.models.seller import Seller


class ProductListing(Base):
    """A marketplace-specific listing linked to a product variant."""

    __tablename__ = "product_listings"

    __table_args__ = (
        UniqueConstraint(
            "platform_id",
            "external_id",
            name="uq_product_listings_platform_external_id",
        ),
        CheckConstraint(
            "current_price >= 0",
            name="ck_product_listings_current_price_non_negative",
        ),
        CheckConstraint(
            "original_price IS NULL OR original_price >= 0",
            name="ck_product_listings_original_price_non_negative",
        ),
        CheckConstraint(
            "rating IS NULL OR (rating >= 0 AND rating <= 5)",
            name="ck_product_listings_rating_range",
        ),
        CheckConstraint(
            "review_count >= 0",
            name="ck_product_listings_review_count_non_negative",
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

    product_variant_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "product_variants.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    seller_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey(
            "sellers.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    external_id: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    title: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        index=True,
    )

    product_url: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    current_price: Mapped[Decimal] = mapped_column(
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

    rating: Mapped[Decimal | None] = mapped_column(
        Numeric(3, 2),
        nullable=True,
    )

    review_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )

    warranty: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    is_available: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
    )

    raw_payload: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )

    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    product_variant: Mapped["ProductVariant"] = relationship(
        back_populates="listings",
    )

    seller: Mapped["Seller | None"] = relationship(
        back_populates="listings",
    )