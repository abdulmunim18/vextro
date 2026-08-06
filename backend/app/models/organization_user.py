"""Membership model connecting users with SME organizations."""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class OrganizationUser(Base):
    """A user's membership and permission inside an organization."""

    __tablename__ = "organization_users"

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "user_id",
            name=(
                "uq_organization_users_"
                "organization_user"
            ),
        ),
        CheckConstraint(
            "membership_role IN "
            "('owner', 'manager', 'analyst')",
            name=(
                "ck_organization_users_"
                "membership_role"
            ),
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

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "users.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    membership_role: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        server_default=text("'analyst'"),
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
        index=True,
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