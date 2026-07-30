from __future__ import annotations
from typing import TYPE_CHECKING
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Identity,
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
    from app.models.product_image import ProductImage
    from app.models.product_variant import ProductVariant
class CanonicalProduct(Base):
    """A standardized real-world product shared across marketplaces."""

    __tablename__ = "canonical_products"

    __table_args__ = (
        UniqueConstraint(
            "brand_id",
            "model",
            name="uq_canonical_products_brand_model",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(),
        primary_key=True,
    )

    category_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "categories.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    brand_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey(
            "brands.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )

    slug: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
    )

    model: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True,
        index=True,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    specifications: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
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

    variants: Mapped[list["ProductVariant"]] = relationship(
        back_populates="canonical_product",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    images: Mapped[list["ProductImage"]] = relationship(
        back_populates="canonical_product",
        passive_deletes=True,
    )