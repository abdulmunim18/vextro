"""The VEXTRO smartphone crawl scheduler.

Behaviour, all of it configurable through the environment:

* ``SCRAPER_ENABLED`` (default ``true``) - run at all.
* ``SCRAPER_RUN_ON_STARTUP`` (default ``true``) - crawl once immediately when
  the scheduler process starts, then fall into the interval.
* ``SCRAPER_INTERVAL_HOURS`` (default ``12``) - how long between crawls.
* ``SCRAPER_SPIDERS`` - comma-separated spider names to run, in order.
* ``SCRAPER_LOCK_PATH`` - where the single-instance lock lives.

The scheduler is a dedicated process: spiders run as subprocesses, so a long
crawl can never block FastAPI request handling. Only one scheduler may exist
at a time, enforced by an operating-system lock rather than by convention,
and APScheduler is configured so a crawl that overruns its window is never
joined by a second one.

Run it with::

    python -m vextro_scraper.scheduler
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading
from datetime import datetime, timedelta
from pathlib import Path

from apscheduler.schedulers.blocking import BlockingScheduler

from vextro_scraper.single_instance import (
    SchedulerAlreadyRunningError,
    SingleInstanceLock,
)


SCRAPER_PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = SCRAPER_PROJECT_ROOT.parent

DEFAULT_SPIDERS = ("priceoye_smartphones", "daraz_smartphones")
JOB_ID = "vextro-marketplace-refresh"

# One crawl at a time, process-wide. The OS lock keeps other processes out;
# this keeps a manually triggered run from overlapping a scheduled one.
_crawl_lock = threading.Lock()


def _environment_flag(name: str, *, default: bool) -> bool:
    """Read a boolean environment flag."""

    raw_value = os.getenv(name)

    if raw_value is None or not raw_value.strip():
        return default

    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


def _interval_hours() -> float:
    """Read the configured crawl interval, falling back to twelve hours."""

    raw_value = os.getenv("SCRAPER_INTERVAL_HOURS", "12")

    try:
        hours = float(raw_value)
    except (TypeError, ValueError):
        hours = 12.0

    # A non-positive interval would make APScheduler crawl continuously.
    return hours if hours > 0 else 12.0


def _configured_spiders() -> tuple[str, ...]:
    """Read the spiders to run, in order."""

    raw_value = os.getenv("SCRAPER_SPIDERS")

    if not raw_value or not raw_value.strip():
        return DEFAULT_SPIDERS

    spiders = tuple(
        name.strip()
        for name in raw_value.split(",")
        if name.strip()
    )

    return spiders or DEFAULT_SPIDERS


def _lock_path() -> Path:
    """Return where the single-instance lock file lives."""

    configured = os.getenv("SCRAPER_LOCK_PATH")

    if configured and configured.strip():
        return Path(configured.strip())

    return REPOSITORY_ROOT / ".runtime" / "scraper-scheduler.lock"


def _log(message: str) -> None:
    print(f"[SCHEDULER] {message}", flush=True)


def trigger_spiders(spiders: tuple[str, ...] | None = None) -> bool:
    """Run every configured spider once, sequentially.

    Returns ``False`` when another crawl is still running, so an overrunning
    crawl is skipped rather than doubled up.
    """

    if not _crawl_lock.acquire(blocking=False):
        _log(
            "Skipped this run because the previous crawl is still in "
            "progress."
        )
        return False

    try:
        started_at = datetime.now()
        _log(
            "Starting automated run at "
            f"{started_at.strftime('%Y-%m-%d %H:%M:%S')}."
        )

        for spider in spiders or _configured_spiders():
            _log(f"Triggering spider: {spider}")

            try:
                subprocess.run(
                    [sys.executable, "-m", "scrapy", "crawl", spider],
                    cwd=SCRAPER_PROJECT_ROOT,
                    capture_output=True,
                    text=True,
                    check=True,
                )
                _log(f"Crawl completed successfully for {spider}.")
            except (subprocess.CalledProcessError, OSError) as error:
                error_output = getattr(error, "stderr", None) or str(error)
                _log(
                    f"Crawl failed for {spider} with error:\n{error_output}"
                )

        _log(
            "Run finished after "
            f"{(datetime.now() - started_at).total_seconds():.0f}s."
        )
        return True
    finally:
        _crawl_lock.release()


def build_scheduler(
    *,
    run_on_startup: bool,
    interval_hours: float,
) -> BlockingScheduler:
    """Return a scheduler configured for the smartphone refresh cycle."""

    scheduler = BlockingScheduler()

    scheduler.add_job(
        trigger_spiders,
        "interval",
        hours=interval_hours,
        id=JOB_ID,
        # ``max_instances`` plus ``coalesce`` mean a crawl that outlives its
        # window is never joined or queued up behind itself.
        max_instances=1,
        coalesce=True,
        misfire_grace_time=3600,
        replace_existing=True,
        next_run_time=(
            datetime.now()
            if run_on_startup
            else datetime.now() + timedelta(hours=interval_hours)
        ),
    )

    return scheduler


def main() -> int:
    """Start the scheduler process, enforcing a single instance."""

    if not _environment_flag("SCRAPER_ENABLED", default=True):
        _log("SCRAPER_ENABLED is false; the scheduler will not start.")
        return 0

    run_on_startup = _environment_flag(
        "SCRAPER_RUN_ON_STARTUP",
        default=True,
    )
    interval_hours = _interval_hours()
    lock = SingleInstanceLock(_lock_path())

    try:
        lock.acquire()
    except SchedulerAlreadyRunningError as error:
        _log(str(error))
        return 0

    try:
        scheduler = build_scheduler(
            run_on_startup=run_on_startup,
            interval_hours=interval_hours,
        )
        next_run = scheduler.get_job(JOB_ID).next_run_time

        _log(
            "VEXTRO crawler scheduler is running "
            f"(run_on_startup={run_on_startup}, "
            f"interval_hours={interval_hours:g}, "
            f"spiders={', '.join(_configured_spiders())}). "
            f"Next run: {next_run:%Y-%m-%d %H:%M:%S}."
        )

        try:
            scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            _log("Scheduler stopped gracefully.")
    finally:
        lock.release()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
