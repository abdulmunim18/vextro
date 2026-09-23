from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.scrape_run import ScrapeRun


class ScrapeError(Base):
    """A bounded, non-sensitive failure recorded for one scrape run."""

    __tablename__ = "scrape_errors"

    __table_args__ = (
        CheckConstraint(
            "error_stage IN ("
            "'fetch', 'parse', 'validation', "
            "'matching', 'delivery', 'ingestion'"
            ")",
            name="ck_scrape_errors_stage_valid",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(),
        primary_key=True,
    )
    scrape_run_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("scrape_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    external_listing_id: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
    )
    product_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    error_type: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
        index=True,
    )
    error_stage: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )
    message: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    raw_value: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
    error_metadata: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )

    scrape_run: Mapped["ScrapeRun"] = relationship(
        back_populates="errors",
    )
