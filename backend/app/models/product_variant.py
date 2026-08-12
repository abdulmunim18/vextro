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
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.canonical_product import CanonicalProduct
    from app.models.price_forecast import PriceForecast
    from app.models.product_listing import ProductListing


class ProductVariant(Base):
    """A specific configuration of a canonical product."""

    __tablename__ = "product_variants"

    __table_args__ = (
        UniqueConstraint(
            "canonical_product_id",
            "ram_gb",
            "storage_gb",
            "color",
            "condition",
            name="uq_product_variants_configuration",
        ),
        CheckConstraint(
            "ram_gb IS NULL OR ram_gb > 0",
            name="ck_product_variants_ram_positive",
        ),
        CheckConstraint(
            "storage_gb IS NULL OR storage_gb > 0",
            name="ck_product_variants_storage_positive",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(),
        primary_key=True,
    )

    canonical_product_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "canonical_products.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    sku: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True,
        unique=True,
        index=True,
    )

    ram_gb: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    storage_gb: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    color: Mapped[str | None] = mapped_column(
        String(80),
        nullable=True,
    )

    condition: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        server_default=text("'new'"),
    )

    variant_attributes: Mapped[dict[str, object]] = mapped_column(
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

    canonical_product: Mapped["CanonicalProduct"] = relationship(
        back_populates="variants",
    )
    listings: Mapped[list["ProductListing"]] = relationship(
        back_populates="product_variant",
    )
    price_forecasts: Mapped[list["PriceForecast"]] = relationship(
        back_populates="product_variant",
        cascade="all, delete-orphan",
    )
