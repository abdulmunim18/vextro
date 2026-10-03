"""Background job scheduler for notification digests and the outbox.

This reuses APScheduler, already the scheduling tool in this project (see
``vextro_scraper/scheduler.py``), rather than introducing a second
scheduling system. It runs in-process inside the FastAPI application and
is off unless ``DIGEST_SCHEDULER_ENABLED`` is true, so the same jobs can
instead be driven by an external cron through
``backend/scripts/run_notification_jobs.py``.

Only one process may run with the scheduler enabled. With several API
workers enabled at once, each would fire the same job; the digest run and
outbox rows are both guarded by unique constraints and row locks, so this
produces wasted work rather than duplicate emails, but a single enabled
process is still the supported setup.
"""

from __future__ import annotations

import logging

from app.core.config import Settings, settings as default_settings
from app.core.database import SessionLocal
from app.models.digest_run import FREQUENCY_DAILY, FREQUENCY_WEEKLY


logger = logging.getLogger(__name__)


_scheduler = None


def run_digest_job(frequency: str) -> None:
    """Run one digest cycle in its own database session."""

    from app.services.digest_service import run_digest_cycle

    database_session = SessionLocal()

    try:
        run_digest_cycle(
            database_session,
            frequency=frequency,
        )

    except Exception:  # noqa: BLE001 - a job must never kill the scheduler
        database_session.rollback()

        logger.exception(
            "scheduler.digest_job_failed frequency=%s",
            frequency,
        )

    finally:
        database_session.close()


def run_outbox_job() -> None:
    """Retry notification deliveries that are still pending or failed."""

    from app.services.notification_dispatcher import (
        dispatch_pending_deliveries,
    )

    database_session = SessionLocal()

    try:
        summary = dispatch_pending_deliveries(database_session)

        if summary["attempted"]:
            logger.info(
                (
                    "scheduler.outbox_job attempted=%s delivered=%s "
                    "failed=%s"
                ),
                summary["attempted"],
                summary["delivered"],
                summary["failed"],
            )

    except Exception:  # noqa: BLE001 - a job must never kill the scheduler
        database_session.rollback()

        logger.exception("scheduler.outbox_job_failed")

    finally:
        database_session.close()


def start_notification_scheduler(
    settings: Settings | None = None,
):
    """Start the background scheduler when it is enabled by configuration."""

    global _scheduler

    active_settings = settings or default_settings

    if not active_settings.digest_scheduler_enabled:
        logger.info("scheduler.disabled")

        return None

    if _scheduler is not None:
        return _scheduler

    from apscheduler.schedulers.background import BackgroundScheduler

    scheduler = BackgroundScheduler(
        timezone=active_settings.digest_zoneinfo,
    )

    scheduler.add_job(
        run_digest_job,
        "cron",
        hour=active_settings.digest_daily_hour,
        minute=0,
        args=[FREQUENCY_DAILY],
        id="vextro-daily-digest",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=3600,
    )

    scheduler.add_job(
        run_digest_job,
        "cron",
        day_of_week=active_settings.digest_weekly_day,
        hour=active_settings.digest_weekly_hour,
        minute=0,
        args=[FREQUENCY_WEEKLY],
        id="vextro-weekly-digest",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=7200,
    )

    scheduler.add_job(
        run_outbox_job,
        "interval",
        seconds=active_settings.notification_outbox_interval_seconds,
        id="vextro-notification-outbox",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=300,
    )

    scheduler.start()

    _scheduler = scheduler

    logger.info(
        (
            "scheduler.started timezone=%s daily_hour=%s "
            "weekly_day=%s weekly_hour=%s outbox_interval=%ss"
        ),
        active_settings.digest_timezone,
        active_settings.digest_daily_hour,
        active_settings.digest_weekly_day,
        active_settings.digest_weekly_hour,
        active_settings.notification_outbox_interval_seconds,
    )

    return scheduler


def shutdown_notification_scheduler() -> None:
    """Stop the background scheduler if it is running."""

    global _scheduler

    if _scheduler is None:
        return

    _scheduler.shutdown(wait=False)
    _scheduler = None

    logger.info("scheduler.stopped")
