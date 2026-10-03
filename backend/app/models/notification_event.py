from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.notification import Notification
    from app.models.user import User


EVENT_TYPE_PRICE_DROP = "price_drop"
EVENT_TYPE_COMPETITOR_RISK = "competitor_risk"
EVENT_TYPE_DIGEST = "digest"


class NotificationEvent(Base):
    """One logical notification occurrence fanned out to delivery channels.

    ``event_key`` is unique so a retried job or a re-processed price
    observation can never produce a second set of deliveries.
    """

    __tablename__ = "notification_events"

    __table_args__ = (
        Index(
            "uq_notification_events_event_key",
            "event_key",
            unique=True,
        ),
        Index(
            "ix_notification_events_user_created_at",
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

    notification_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey(
            "notifications.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    event_key: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    event_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )

    title: Mapped[str] = mapped_column(
        String(180),
        nullable=False,
    )

    body: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    action_path: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    user: Mapped["User"] = relationship()

    notification: Mapped["Notification | None"] = relationship()
