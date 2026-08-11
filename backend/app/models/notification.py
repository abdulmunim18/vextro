from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.canonical_product import CanonicalProduct
    from app.models.price_alert import PriceAlert
    from app.models.user import User


class Notification(Base):
    """An in-app notification delivered to a VEXTRO user."""

    __tablename__ = "notifications"

    __table_args__ = (
        Index(
            "ix_notifications_user_read",
            "user_id",
            "is_read",
        ),
        Index(
            "ix_notifications_user_created_at",
            "user_id",
            "created_at",
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
        index=True,
    )

    price_alert_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey(
            "price_alerts.id",
            ondelete="SET NULL",
        ),
        nullable=True,
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

    notification_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )

    title: Mapped[str] = mapped_column(
        String(180),
        nullable=False,
    )

    message: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    action_path: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    is_read: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
    )

    read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    user: Mapped["User"] = relationship()

    price_alert: Mapped["PriceAlert | None"] = relationship()

    canonical_product: Mapped["CanonicalProduct | None"] = relationship()