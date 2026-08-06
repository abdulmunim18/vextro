"""Sales CSV import jobs created by SME organizations."""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SalesImport(Base):
    """One CSV sales-import operation for an SME organization."""

    __tablename__ = "sales_imports"

    __table_args__ = (
        CheckConstraint(
            "total_rows >= 0",
            name="ck_sales_imports_total_rows_non_negative",
        ),
        CheckConstraint(
            "accepted_rows >= 0",
            name="ck_sales_imports_accepted_rows_non_negative",
        ),
        CheckConstraint(
            "rejected_rows >= 0",
            name="ck_sales_imports_rejected_rows_non_negative",
        ),
        CheckConstraint(
            "accepted_rows + rejected_rows <= total_rows",
            name="ck_sales_imports_processed_rows_within_total",
        ),
        CheckConstraint(
            (
                "status IN ("
                "'pending', "
                "'processing', "
                "'completed', "
                "'completed_with_errors', "
                "'failed'"
                ")"
            ),
            name="ck_sales_imports_status_valid",
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

    uploaded_by_user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "users.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    original_filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        server_default=text("'pending'"),
        index=True,
    )

    total_rows: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )

    accepted_rows: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )

    rejected_rows: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )

    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )