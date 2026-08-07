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
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.canonical_product import CanonicalProduct
    from app.models.product_listing import ProductListing


class ProductImage(Base):
    """An image belonging to a canonical product or marketplace listing."""

    __tablename__ = "product_images"

    __table_args__ = (
        CheckConstraint(
            """
            (
                canonical_product_id IS NOT NULL
                AND listing_id IS NULL
            )
            OR
            (
                canonical_product_id IS NULL
                AND listing_id IS NOT NULL
            )
            """,
            name="ck_product_images_exactly_one_owner",
        ),
        CheckConstraint(
            "sort_order >= 0",
            name="ck_product_images_sort_order_non_negative",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(),
        primary_key=True,
    )

    canonical_product_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey(
            "canonical_products.id",
            ondelete="CASCADE",
        ),
        nullable=True,
        index=True,
    )

    listing_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey(
            "product_listings.id",
            ondelete="CASCADE",
        ),
        nullable=True,
        index=True,
    )

    image_url: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    alt_text: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    is_primary: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
    )

    sort_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    canonical_product: Mapped["CanonicalProduct | None"] = relationship(
        back_populates="images",
    )

    listing: Mapped["ProductListing | None"] = relationship(
        back_populates="images",
    )