"""Products managed by an SME organization."""

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
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class BusinessProduct(Base):
    """An organization's product mapped to the VEXTRO catalog."""

    __tablename__ = "business_products"

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "sku",
            name="uq_business_products_organization_sku",
        ),
        CheckConstraint(
            "cost_price IS NULL OR cost_price >= 0",
            name="ck_business_products_cost_price_non_negative",
        ),
        CheckConstraint(
            "selling_price IS NULL OR selling_price >= 0",
            name="ck_business_products_selling_price_non_negative",
        ),
        CheckConstraint(
            "stock_level >= 0",
            name="ck_business_products_stock_level_non_negative",
        ),
        CheckConstraint(
            "reorder_level >= 0",
            name="ck_business_products_reorder_level_non_negative",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(),
        primary_key=True,
    )

    organization_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "organizations.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    canonical_product_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey(
            "canonical_products.id",
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

    sku: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True,
        index=True,
    )

    cost_price: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 2),
        nullable=True,
    )

    selling_price: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 2),
        nullable=True,
    )

    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        server_default=text("'PKR'"),
    )

    stock_level: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )

    reorder_level: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
        index=True,
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