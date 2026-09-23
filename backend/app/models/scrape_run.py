from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Identity,
    Integer,
    String,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.scrape_error import ScrapeError


class ScrapeRun(Base):
    """One durable Daraz or PriceOye spider execution."""

    __tablename__ = "scrape_runs"

    __table_args__ = (
        CheckConstraint(
            "platform IN ('daraz', 'priceoye')",
            name="ck_scrape_runs_platform_valid",
        ),
        CheckConstraint(
            "status IN ('running', 'completed', 'partial', 'failed')",
            name="ck_scrape_runs_status_valid",
        ),
        CheckConstraint(
            "trigger_type IN ('manual', 'scheduler', 'test')",
            name="ck_scrape_runs_trigger_type_valid",
        ),
        CheckConstraint(
            "items_discovered >= 0",
            name="ck_scrape_runs_discovered_non_negative",
        ),
        CheckConstraint(
            "items_ingested >= 0",
            name="ck_scrape_runs_ingested_non_negative",
        ),
        CheckConstraint(
            "items_rejected >= 0",
            name="ck_scrape_runs_rejected_non_negative",
        ),
        CheckConstraint(
            "items_failed >= 0",
            name="ck_scrape_runs_failed_non_negative",
        ),
        CheckConstraint(
            "error_count >= 0",
            name="ck_scrape_runs_error_count_non_negative",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(),
        primary_key=True,
    )
    platform: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
    )
    spider_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'running'"),
        index=True,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    items_discovered: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )
    items_ingested: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )
    items_rejected: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )
    items_failed: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )
    error_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )
    trigger_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'manual'"),
    )
    parser_version: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
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

    errors: Mapped[list["ScrapeError"]] = relationship(
        back_populates="scrape_run",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ScrapeError.created_at",
    )
