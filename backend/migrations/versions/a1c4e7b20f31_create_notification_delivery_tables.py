"""create notification delivery tables

Revision ID: a1c4e7b20f31
Revises: d8f2b4c10e95
Create Date: 2026-10-03 10:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "a1c4e7b20f31"
down_revision: Union[str, Sequence[str], None] = "d8f2b4c10e95"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notification_preferences",
        sa.Column(
            "id",
            sa.BigInteger(),
            sa.Identity(),
            nullable=False,
        ),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "price_alert_email",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "price_alert_push",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "competitor_alert_email",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "competitor_alert_push",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "digest_frequency",
            sa.String(length=10),
            server_default=sa.text("'off'"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "digest_frequency IN ('off', 'daily', 'weekly')",
            name="ck_notification_preferences_digest_frequency",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index(
        op.f("ix_notification_preferences_user_id"),
        "notification_preferences",
        ["user_id"],
        unique=False,
    )

    op.create_table(
        "push_subscriptions",
        sa.Column(
            "id",
            sa.BigInteger(),
            sa.Identity(),
            nullable=False,
        ),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("endpoint", sa.Text(), nullable=False),
        sa.Column("endpoint_hash", sa.String(length=64), nullable=False),
        sa.Column("p256dh_key", sa.String(length=255), nullable=False),
        sa.Column("auth_key", sa.String(length=255), nullable=False),
        sa.Column("user_agent", sa.String(length=255), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "last_delivered_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "deactivated_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
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
        op.f("ix_push_subscriptions_user_id"),
        "push_subscriptions",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_push_subscriptions_user_active",
        "push_subscriptions",
        ["user_id", "is_active"],
        unique=False,
    )
    op.create_index(
        "uq_push_subscriptions_endpoint",
        "push_subscriptions",
        ["endpoint_hash"],
        unique=True,
    )

    op.create_table(
        "notification_events",
        sa.Column(
            "id",
            sa.BigInteger(),
            sa.Identity(),
            nullable=False,
        ),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("notification_id", sa.BigInteger(), nullable=True),
        sa.Column("event_key", sa.String(length=200), nullable=False),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("body", sa.String(length=500), nullable=False),
        sa.Column("action_path", sa.String(length=255), nullable=True),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["notification_id"],
            ["notifications.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_notification_events_user_id"),
        "notification_events",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_notification_events_notification_id"),
        "notification_events",
        ["notification_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_notification_events_event_type"),
        "notification_events",
        ["event_type"],
        unique=False,
    )
    op.create_index(
        "ix_notification_events_user_created_at",
        "notification_events",
        ["user_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "uq_notification_events_event_key",
        "notification_events",
        ["event_key"],
        unique=True,
    )

    op.create_table(
        "notification_deliveries",
        sa.Column(
            "id",
            sa.BigInteger(),
            sa.Identity(),
            nullable=False,
        ),
        sa.Column("event_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("channel", sa.String(length=20), nullable=False),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column(
            "attempts",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "attempted_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "delivered_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "attempts >= 0",
            name="ck_notification_deliveries_attempts_non_negative",
        ),
        sa.CheckConstraint(
            "channel IN ('in_app', 'email', 'web_push')",
            name="ck_notification_deliveries_channel",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'delivered', 'failed', 'skipped')",
            name="ck_notification_deliveries_status",
        ),
        sa.ForeignKeyConstraint(
            ["event_id"],
            ["notification_events.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_notification_deliveries_event_id"),
        "notification_deliveries",
        ["event_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_notification_deliveries_user_id"),
        "notification_deliveries",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_notification_deliveries_status_channel",
        "notification_deliveries",
        ["status", "channel"],
        unique=False,
    )
    op.create_index(
        "uq_notification_deliveries_event_channel",
        "notification_deliveries",
        ["event_id", "channel"],
        unique=True,
    )

    op.create_table(
        "digest_runs",
        sa.Column(
            "id",
            sa.BigInteger(),
            sa.Identity(),
            nullable=False,
        ),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("frequency", sa.String(length=10), nullable=False),
        sa.Column("period_key", sa.String(length=30), nullable=False),
        sa.Column(
            "period_start",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "period_end",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column(
            "event_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "event_count >= 0",
            name="ck_digest_runs_event_count_non_negative",
        ),
        sa.CheckConstraint(
            "frequency IN ('daily', 'weekly')",
            name="ck_digest_runs_frequency",
        ),
        sa.CheckConstraint(
            "status IN ('delivered', 'skipped_empty', 'failed')",
            name="ck_digest_runs_status",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_digest_runs_user_id"),
        "digest_runs",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "uq_digest_runs_user_frequency_period",
        "digest_runs",
        ["user_id", "frequency", "period_key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "uq_digest_runs_user_frequency_period",
        table_name="digest_runs",
    )
    op.drop_index(
        op.f("ix_digest_runs_user_id"),
        table_name="digest_runs",
    )
    op.drop_table("digest_runs")

    op.drop_index(
        "uq_notification_deliveries_event_channel",
        table_name="notification_deliveries",
    )
    op.drop_index(
        "ix_notification_deliveries_status_channel",
        table_name="notification_deliveries",
    )
    op.drop_index(
        op.f("ix_notification_deliveries_user_id"),
        table_name="notification_deliveries",
    )
    op.drop_index(
        op.f("ix_notification_deliveries_event_id"),
        table_name="notification_deliveries",
    )
    op.drop_table("notification_deliveries")

    op.drop_index(
        "uq_notification_events_event_key",
        table_name="notification_events",
    )
    op.drop_index(
        "ix_notification_events_user_created_at",
        table_name="notification_events",
    )
    op.drop_index(
        op.f("ix_notification_events_event_type"),
        table_name="notification_events",
    )
    op.drop_index(
        op.f("ix_notification_events_notification_id"),
        table_name="notification_events",
    )
    op.drop_index(
        op.f("ix_notification_events_user_id"),
        table_name="notification_events",
    )
    op.drop_table("notification_events")

    op.drop_index(
        "uq_push_subscriptions_endpoint",
        table_name="push_subscriptions",
    )
    op.drop_index(
        "ix_push_subscriptions_user_active",
        table_name="push_subscriptions",
    )
    op.drop_index(
        op.f("ix_push_subscriptions_user_id"),
        table_name="push_subscriptions",
    )
    op.drop_table("push_subscriptions")

    op.drop_index(
        op.f("ix_notification_preferences_user_id"),
        table_name="notification_preferences",
    )
    op.drop_table("notification_preferences")
