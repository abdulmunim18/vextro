"""Create refresh tokens table.

Revision ID: 6162266037b2
Revises: 9b6809b701b5
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "6162266037b2"
down_revision: str | None = "9b6809b701b5"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    """Create the refresh-token session table."""

    op.create_table(
        "refresh_tokens",
        sa.Column(
            "id",
            sa.BigInteger(),
            sa.Identity(always=False),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            nullable=False,
        ),
        sa.Column(
            "token_hash",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "revoked_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_refresh_tokens_token_hash",
        "refresh_tokens",
        ["token_hash"],
        unique=True,
    )

    op.create_index(
        "ix_refresh_tokens_user_id",
        "refresh_tokens",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    """Remove the refresh-token session table."""

    op.drop_index(
        "ix_refresh_tokens_user_id",
        table_name="refresh_tokens",
    )

    op.drop_index(
        "ix_refresh_tokens_token_hash",
        table_name="refresh_tokens",
    )

    op.drop_table("refresh_tokens")