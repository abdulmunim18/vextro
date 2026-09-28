from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Integer,
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
    from app.models.user import User


class PendingProductMatch(Base):
    """A marketplace listing awaiting a safe catalog assignment."""

    __tablename__ = "pending_product_matches"

    __table_args__ = (
        UniqueConstraint(
            "platform_code",
            "external_id",
            name="uq_pending_product_matches_platform_external_id",
        ),
        CheckConstraint(
            "platform_code IN ('daraz', 'priceoye')",
            name="ck_pending_product_matches_platform_valid",
        ),
        CheckConstraint(
            "status IN ('pending', 'resolved', 'replayed', 'dismissed')",
            name="ck_pending_product_matches_status_valid",
        ),
        CheckConstraint(
            "match_confidence BETWEEN 0 AND 100",
            name="ck_pending_product_matches_confidence_range",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(),
        primary_key=True,
    )
    platform_code: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
    )
    external_id: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    product_url: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    match_payload: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        nullable=False,
    )
    listing_payload: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        nullable=False,
    )
    match_confidence: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )
    match_reason: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    suggested_product_variant_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("product_variants.id", ondelete="SET NULL"),
        nullable=True,
    )
    assigned_product_variant_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("product_variants.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'pending'"),
        index=True,
    )
    resolved_by_user_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    replayed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    replay_result: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
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

    suggested_product_variant: Mapped["ProductVariant | None"] = relationship(
        foreign_keys=[suggested_product_variant_id],
    )
    assigned_product_variant: Mapped["ProductVariant | None"] = relationship(
        foreign_keys=[assigned_product_variant_id],
    )
    resolved_by_user: Mapped["User | None"] = relationship(
        foreign_keys=[resolved_by_user_id],
    )
