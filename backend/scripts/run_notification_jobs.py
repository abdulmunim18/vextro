"""Run VEXTRO notification background jobs once and exit.

Use this when the in-process scheduler is disabled and an external cron,
Windows Task Scheduler or container entrypoint drives the jobs instead.

    python -m scripts.run_notification_jobs daily-digest
    python -m scripts.run_notification_jobs weekly-digest
    python -m scripts.run_notification_jobs outbox

Each command is safe to run more often than its schedule: the digest run
table and the delivery outbox are both idempotent.
"""

from __future__ import annotations

import argparse
import logging
import sys

from app.core.database import SessionLocal
from app.models.digest_run import FREQUENCY_DAILY, FREQUENCY_WEEKLY
from app.services.digest_service import run_digest_cycle
from app.services.notification_dispatcher import (
    dispatch_pending_deliveries,
)


def main(argv: list[str] | None = None) -> int:
    """Run the requested notification job."""

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    parser = argparse.ArgumentParser(
        description="Run one VEXTRO notification background job.",
    )
    parser.add_argument(
        "job",
        choices=[
            "daily-digest",
            "weekly-digest",
            "outbox",
        ],
    )

    arguments = parser.parse_args(argv)

    database_session = SessionLocal()

    try:
        if arguments.job == "daily-digest":
            summary = run_digest_cycle(
                database_session,
                frequency=FREQUENCY_DAILY,
            )

        elif arguments.job == "weekly-digest":
            summary = run_digest_cycle(
                database_session,
                frequency=FREQUENCY_WEEKLY,
            )

        else:
            summary = dispatch_pending_deliveries(
                database_session,
            )

        print(summary)

    except Exception:
        database_session.rollback()

        logging.getLogger(__name__).exception(
            "notification job failed: %s",
            arguments.job,
        )

        return 1

    finally:
        database_session.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
