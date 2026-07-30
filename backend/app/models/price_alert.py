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
    Integer,
    Numeric,
    String,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.canonical_product import CanonicalProduct
    from app.models.product_listing import ProductListing
    from app.models.user import User


class PriceAlert(Base):
    """A consumer alert for a product or listing target price."""

    __tablename__ = "price_alerts"

    __table_args__ = (
        CheckConstraint(
            "target_price > 0",
            name="ck_price_alerts_target_price_positive",
        ),
        CheckConstraint(
            "char_length(currency) = 3",
            name="ck_price_alerts_currency_length",
        ),
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
            name="ck_price_alerts_exactly_one_target",
        ),
        CheckConstraint(
            "notification_count >= 0",
            name="ck_price_alerts_notification_count_non_negative",
        ),
        Index(
            "ix_price_alerts_user_active",
            "user_id",
            "is_active",
        ),
        Index(
            "uq_price_alerts_active_product_target",
            "user_id",
            "canonical_product_id",
            unique=True,
            postgresql_where=text(
                "is_active = true "
                "AND canonical_product_id IS NOT NULL"
            ),
        ),
        Index(
            "uq_price_alerts_active_listing_target",
            "user_id",
            "listing_id",
            unique=True,
            postgresql_where=text(
                "is_active = true "
                "AND listing_id IS NOT NULL"
            ),
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(),
        primary_key=True,
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "users.id",
            ondelete="CASCADE",
        ),
        nullable=False,
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

    target_price: Mapped[Decimal] = mapped_column(
        Numeric(14, 2),
        nullable=False,
    )

    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        server_default=text("'PKR'"),
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
    )

    is_triggered: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
    )

    notification_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )

    last_checked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    triggered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    last_notified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
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

    user: Mapped["User"] = relationship()

    canonical_product: Mapped["CanonicalProduct | None"] = relationship()

    listing: Mapped["ProductListing | None"] = relationship()