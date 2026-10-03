"""Tests for the crawl scheduler's startup, interval and single-instance rules."""

from datetime import datetime, timedelta

import pytest

from vextro_scraper import scheduler
from vextro_scraper.single_instance import (
    SchedulerAlreadyRunningError,
    SingleInstanceLock,
)


@pytest.fixture(autouse=True)
def clear_scheduler_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Start each test from the documented defaults."""

    for name in (
        "SCRAPER_ENABLED",
        "SCRAPER_RUN_ON_STARTUP",
        "SCRAPER_INTERVAL_HOURS",
        "SCRAPER_SPIDERS",
        "SCRAPER_LOCK_PATH",
    ):
        monkeypatch.delenv(name, raising=False)


# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------


def test_defaults_match_the_documented_behaviour():
    """Enabled, crawl on startup, then every twelve hours, both platforms."""

    assert scheduler._environment_flag("SCRAPER_ENABLED", default=True) is True
    assert (
        scheduler._environment_flag("SCRAPER_RUN_ON_STARTUP", default=True)
        is True
    )
    assert scheduler._interval_hours() == 12.0
    assert scheduler._configured_spiders() == (
        "priceoye_smartphones",
        "daraz_smartphones",
    )


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("true", True),
        ("True", True),
        ("1", True),
        ("yes", True),
        ("on", True),
        ("false", False),
        ("0", False),
        ("no", False),
        ("", True),
    ],
)
def test_flags_read_every_reasonable_spelling(
    monkeypatch: pytest.MonkeyPatch,
    raw: str,
    expected: bool,
) -> None:
    monkeypatch.setenv("SCRAPER_ENABLED", raw)

    assert (
        scheduler._environment_flag("SCRAPER_ENABLED", default=True)
        is expected
    )


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("6", 6.0), ("0.5", 0.5), ("12", 12.0), ("0", 12.0), ("-3", 12.0),
     ("not-a-number", 12.0)],
)
def test_interval_rejects_values_that_would_crawl_continuously(
    monkeypatch: pytest.MonkeyPatch,
    raw: str,
    expected: float,
) -> None:
    monkeypatch.setenv("SCRAPER_INTERVAL_HOURS", raw)

    assert scheduler._interval_hours() == expected


def test_spider_list_is_configurable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SCRAPER_SPIDERS", " daraz_smartphones , , ")

    assert scheduler._configured_spiders() == ("daraz_smartphones",)


# --------------------------------------------------------------------------
# Startup run and the twelve-hour interval
# --------------------------------------------------------------------------


def test_startup_run_is_scheduled_immediately_then_every_interval():
    """One run now, the next one twelve hours later."""

    # The scheduler is configured but never started, so nothing crawls here.
    job = scheduler.build_scheduler(
        run_on_startup=True,
        interval_hours=12,
    ).get_job(scheduler.JOB_ID)

    assert job is not None
    assert job.next_run_time <= datetime.now(job.next_run_time.tzinfo)
    assert job.trigger.interval == timedelta(hours=12)
    assert job.max_instances == 1
    assert job.coalesce is True


def test_without_a_startup_run_the_first_crawl_waits_one_interval():
    job = scheduler.build_scheduler(
        run_on_startup=False,
        interval_hours=12,
    ).get_job(scheduler.JOB_ID)
    now = datetime.now(job.next_run_time.tzinfo)

    assert job.next_run_time > now + timedelta(hours=11)


def test_disabled_scheduler_never_takes_the_lock(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    """SCRAPER_ENABLED=false exits before scheduling or locking anything."""

    lock_path = tmp_path / "scheduler.lock"
    monkeypatch.setenv("SCRAPER_ENABLED", "false")
    monkeypatch.setenv("SCRAPER_LOCK_PATH", str(lock_path))

    assert scheduler.main() == 0
    assert not lock_path.exists()


# --------------------------------------------------------------------------
# Part 16 - duplicate schedulers and overlapping crawls
# --------------------------------------------------------------------------


def test_a_second_scheduler_process_cannot_take_the_lock(tmp_path) -> None:
    """Two schedulers would mean two overlapping twelve-hour crawls."""

    lock_path = tmp_path / "scheduler.lock"
    first = SingleInstanceLock(lock_path)
    first.acquire()

    try:
        with pytest.raises(SchedulerAlreadyRunningError):
            SingleInstanceLock(lock_path).acquire()
    finally:
        first.release()

    # Releasing hands the lock to the next process cleanly.
    second = SingleInstanceLock(lock_path)
    second.acquire()
    second.release()


def test_main_exits_quietly_when_another_scheduler_holds_the_lock(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    """A duplicate launch is a no-op, not a crash and not a second crawler."""

    lock_path = tmp_path / "scheduler.lock"
    monkeypatch.setenv("SCRAPER_LOCK_PATH", str(lock_path))

    started: list[bool] = []
    monkeypatch.setattr(
        scheduler,
        "build_scheduler",
        lambda **_: started.append(True),
    )

    holder = SingleInstanceLock(lock_path)
    holder.acquire()

    try:
        assert scheduler.main() == 0
        assert started == []
    finally:
        holder.release()


def test_an_overrunning_crawl_is_skipped_not_doubled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A crawl still running when the next one fires does not stack up."""

    monkeypatch.setenv("SCRAPER_SPIDERS", "daraz_smartphones")

    attempts: list[bool] = []

    def fake_run(*_args, **_kwargs):
        # Re-entering while the first crawl holds the lock must be refused.
        attempts.append(scheduler.trigger_spiders())

        class _Completed:
            stderr = ""

        return _Completed()

    monkeypatch.setattr(scheduler.subprocess, "run", fake_run)

    assert scheduler.trigger_spiders() is True
    assert attempts == [False]


def test_a_failing_spider_does_not_stop_the_other_platform(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One marketplace being down must not cancel the other's refresh."""

    monkeypatch.setenv(
        "SCRAPER_SPIDERS",
        "priceoye_smartphones,daraz_smartphones",
    )

    attempted: list[str] = []

    def fake_run(command, **_kwargs):
        spider = command[-1]
        attempted.append(spider)

        if spider == "priceoye_smartphones":
            raise OSError("marketplace unreachable")

        class _Completed:
            stderr = ""

        return _Completed()

    monkeypatch.setattr(scheduler.subprocess, "run", fake_run)

    assert scheduler.trigger_spiders() is True
    assert attempted == ["priceoye_smartphones", "daraz_smartphones"]
