"""Validated sales rows stored from SME CSV imports."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
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


class SalesRecord(Base):
    """One accepted sales row belonging to a CSV import."""

    __tablename__ = "sales_records"

    __table_args__ = (
        UniqueConstraint(
            "sales_import_id",
            "source_row_number",
            name="uq_sales_records_import_source_row",
        ),
        CheckConstraint(
            "source_row_number >= 1",
            name="ck_sales_records_source_row_positive",
        ),
        CheckConstraint(
            "quantity > 0",
            name="ck_sales_records_quantity_positive",
        ),
        CheckConstraint(
            "unit_price >= 0",
            name="ck_sales_records_unit_price_non_negative",
        ),
        CheckConstraint(
            "total_revenue >= 0",
            name="ck_sales_records_total_revenue_non_negative",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(),
        primary_key=True,
    )

    sales_import_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "sales_imports.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    business_product_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "business_products.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    source_row_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    sale_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )

    quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    unit_price: Mapped[Decimal] = mapped_column(
        Numeric(14, 2),
        nullable=False,
    )

    total_revenue: Mapped[Decimal] = mapped_column(
        Numeric(16, 2),
        nullable=False,
    )

    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        server_default=text("'PKR'"),
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )