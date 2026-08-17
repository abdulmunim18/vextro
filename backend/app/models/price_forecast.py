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
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.product_variant import ProductVariant


class PriceForecast(Base):
    """Versioned price forecast published by the ML integration."""

    __tablename__ = "price_forecasts"

    __table_args__ = (
        CheckConstraint(
            "horizon_days > 0",
            name="ck_price_forecasts_horizon_positive",
        ),
        CheckConstraint(
            "training_observation_count > 0",
            name="ck_price_forecasts_observations_positive",
        ),
        CheckConstraint(
            "char_length(currency) = 3",
            name="ck_price_forecasts_currency_length",
        ),
        CheckConstraint(
            "confidence IN ('low', 'medium', 'high')",
            name="ck_price_forecasts_confidence",
        ),
        CheckConstraint(
            "mae IS NULL OR mae >= 0",
            name="ck_price_forecasts_mae_non_negative",
        ),
        CheckConstraint(
            "rmse IS NULL OR rmse >= 0",
            name="ck_price_forecasts_rmse_non_negative",
        ),
        CheckConstraint(
            "mape IS NULL OR mape >= 0",
            name="ck_price_forecasts_mape_non_negative",
        ),
        Index(
            "ix_price_forecasts_variant_active_generated",
            "product_variant_id",
            "is_active",
            "generated_at",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(),
        primary_key=True,
    )
    product_variant_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("product_variants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    model_name: Mapped[str] = mapped_column(String(80), nullable=False)
    model_version: Mapped[str] = mapped_column(String(80), nullable=False)
    horizon_days: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        server_default=text("'PKR'"),
    )
    training_observation_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    training_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    training_ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    mae: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    rmse: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    mape: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    confidence: Mapped[str] = mapped_column(String(20), nullable=False)
    forecast_points: Mapped[list[dict[str, object]]] = mapped_column(
        JSONB,
        nullable=False,
    )
    limitations: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
    )
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
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

    product_variant: Mapped["ProductVariant"] = relationship(
        back_populates="price_forecasts",
    )
