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
    from app.models.user import User


FREQUENCY_DAILY = "daily"
FREQUENCY_WEEKLY = "weekly"

DIGEST_STATUS_DELIVERED = "delivered"
DIGEST_STATUS_SKIPPED_EMPTY = "skipped_empty"
DIGEST_STATUS_FAILED = "failed"


class DigestRun(Base):
    """One digest reporting period processed for one user.

    ``(user_id, frequency, period_key)`` is unique so a scheduler that
    fires twice for the same period cannot send a second digest email.
    """

    __tablename__ = "digest_runs"

    __table_args__ = (
        CheckConstraint(
            "frequency IN ('daily', 'weekly')",
            name="ck_digest_runs_frequency",
        ),
        CheckConstraint(
            "status IN ('delivered', 'skipped_empty', 'failed')",
            name="ck_digest_runs_status",
        ),
        CheckConstraint(
            "event_count >= 0",
            name="ck_digest_runs_event_count_non_negative",
        ),
        Index(
            "uq_digest_runs_user_frequency_period",
            "user_id",
            "frequency",
            "period_key",
            unique=True,
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

    frequency: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
    )

    period_key: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    period_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    period_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    event_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
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

    user: Mapped["User"] = relationship()
