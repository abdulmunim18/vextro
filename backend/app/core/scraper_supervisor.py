"""Optionally launch the scraper scheduler alongside the API.

The scheduler is a separate process by design: a smartphone crawl takes
minutes and must never sit inside the event loop serving requests. For local
development it is still convenient for "start the project" to mean one
command, so the API can spawn that process on startup.

Spawning is opt-in (``SCRAPER_AUTOSTART_WITH_API``) and safe to repeat.
``uvicorn --reload`` restarts the application process on every file change,
and multiple workers each run this code, so the guard matters: the scheduler
takes an operating-system lock on startup and a second copy exits immediately
without scheduling anything.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path

from app.core.config import settings


logger = logging.getLogger(__name__)

BACKEND_ROOT = Path(__file__).resolve().parents[2]
REPOSITORY_ROOT = BACKEND_ROOT.parent
SCRAPER_ROOT = REPOSITORY_ROOT / "vextro_scraper"


class ScraperSchedulerSupervisor:
    """Start and stop the scheduler process that belongs to this API run."""

    def __init__(self) -> None:
        self._process: subprocess.Popen[bytes] | None = None

    @property
    def is_running(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def start(self) -> subprocess.Popen[bytes] | None:
        """Launch the scheduler process, when configured and available."""

        if not settings.scraper_autostart_with_api:
            return None

        if not settings.scraper_enabled:
            logger.info(
                "Scraper scheduler autostart skipped: SCRAPER_ENABLED "
                "is false."
            )
            return None

        if self.is_running:
            return self._process

        if not (SCRAPER_ROOT / "vextro_scraper" / "scheduler.py").exists():
            logger.warning(
                "Scraper scheduler autostart skipped: %s is missing.",
                SCRAPER_ROOT,
            )
            return None

        environment = {
            **os.environ,
            "VEXTRO_SCRAPE_TRIGGER": "scheduler",
            "SCRAPER_ENABLED": "true",
            "SCRAPER_RUN_ON_STARTUP": (
                "true" if settings.scraper_run_on_startup else "false"
            ),
            "SCRAPER_INTERVAL_HOURS": str(settings.scraper_interval_hours),
        }

        if settings.ingestion_api_key:
            environment["INGESTION_API_KEY"] = settings.ingestion_api_key

        if settings.scraper_lock_path:
            environment["SCRAPER_LOCK_PATH"] = settings.scraper_lock_path

        try:
            self._process = subprocess.Popen(
                [sys.executable, "-m", "vextro_scraper.scheduler"],
                cwd=SCRAPER_ROOT,
                env=environment,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except OSError:
            logger.exception("Scraper scheduler could not be launched.")
            return None

        logger.info(
            "Scraper scheduler launched (pid=%s, run_on_startup=%s, "
            "interval_hours=%s). A second instance exits on its own lock.",
            self._process.pid,
            settings.scraper_run_on_startup,
            settings.scraper_interval_hours,
        )

        return self._process

    def stop(self) -> None:
        """Terminate the scheduler process this API run launched."""

        process = self._process
        self._process = None

        if process is None or process.poll() is not None:
            return

        process.terminate()

        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()

        logger.info("Scraper scheduler stopped.")


scraper_scheduler_supervisor = ScraperSchedulerSupervisor()
