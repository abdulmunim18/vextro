from __future__ import annotations
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    Identity,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ScrapeRun(Base):
    """Audit log tracking scraper executions, status, item counts, and runtime errors."""

    __tablename__ = "scrape_runs"

    id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(),
        primary_key=True,
    )

    platform: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )  # e.g., 'PriceOye', 'Daraz', 'Mega.pk'

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'RUNNING'"),
        index=True,
    )  # 'RUNNING', 'SUCCESS', 'FAILED', 'CANCELLED'

    triggered_by: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        server_default=text("'MANUAL'"),
    )  # 'SCHEDULED', 'MANUAL', 'PIPELINE'

    items_scraped: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )

    items_failed: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )

    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
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
