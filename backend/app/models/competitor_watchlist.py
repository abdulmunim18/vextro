"""Competitor listings monitored by SME organizations."""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Identity,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class CompetitorWatchlist(Base):
    """Connect an SME product with a competitor listing."""

    __tablename__ = "competitor_watchlists"

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "business_product_id",
            "listing_id",
            name=(
                "uq_competitor_watchlists_"
                "organization_product_listing"
            ),
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

    business_product_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "business_products.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    listing_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "product_listings.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
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