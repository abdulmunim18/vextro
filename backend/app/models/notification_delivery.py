from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.notification_event import NotificationEvent


CHANNEL_IN_APP = "in_app"
CHANNEL_EMAIL = "email"
CHANNEL_WEB_PUSH = "web_push"

STATUS_PENDING = "pending"
STATUS_DELIVERED = "delivered"
STATUS_FAILED = "failed"
STATUS_SKIPPED = "skipped"


class NotificationDelivery(Base):
    """Per-channel delivery outcome for one notification event.

    Rows are written inside the business transaction and dispatched after
    it commits, so this table doubles as a transactional outbox.
    """

    __tablename__ = "notification_deliveries"

    __table_args__ = (
        CheckConstraint(
            "channel IN ('in_app', 'email', 'web_push')",
            name="ck_notification_deliveries_channel",
        ),
        CheckConstraint(
            "status IN ('pending', 'delivered', 'failed', 'skipped')",
            name="ck_notification_deliveries_status",
        ),
        CheckConstraint(
            "attempts >= 0",
            name="ck_notification_deliveries_attempts_non_negative",
        ),
        Index(
            "uq_notification_deliveries_event_channel",
            "event_id",
            "channel",
            unique=True,
        ),
        Index(
            "ix_notification_deliveries_status_channel",
            "status",
            "channel",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(),
        primary_key=True,
    )

    event_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "notification_events.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
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

    channel: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'pending'"),
    )

    attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )

    attempted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    delivered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    failure_reason: Mapped[str | None] = mapped_column(
        Text,
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

    event: Mapped["NotificationEvent"] = relationship()
