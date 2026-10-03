"""A cross-platform single-instance lock for the scraper scheduler.

Two schedulers would mean two overlapping twelve-hour crawls writing to the
same listings. A FastAPI ``--reload`` worker restarting, a second terminal, a
Windows login task firing while a developer already has the project running:
each is an ordinary way to end up with two. The lock makes that impossible
rather than unlikely.

The lock is held by an operating-system file lock, not by the presence of a
file, so a scheduler killed without cleanup releases it automatically instead
of leaving a stale PID behind.
"""

from __future__ import annotations

import os
from pathlib import Path


class SchedulerAlreadyRunningError(RuntimeError):
    """Another scheduler process already holds the lock."""


class SingleInstanceLock:
    """Hold an exclusive OS-level lock for the lifetime of a process."""

    def __init__(self, lock_path: str | os.PathLike[str]) -> None:
        self.lock_path = Path(lock_path)
        self._handle = None

    def acquire(self) -> None:
        """Take the lock, or raise :class:`SchedulerAlreadyRunningError`."""

        self.lock_path.parent.mkdir(parents=True, exist_ok=True)

        # Open read/write without truncating, so the byte the lock covers has
        # a stable position whether or not the file already existed.
        handle = os.fdopen(
            os.open(self.lock_path, os.O_RDWR | os.O_CREAT),
            "r+",
            encoding="utf-8",
        )
        handle.seek(0)

        try:
            self._lock_exclusive(handle)
        except OSError as exc:
            handle.close()
            raise SchedulerAlreadyRunningError(
                "Another VEXTRO scraper scheduler already holds "
                f"{self.lock_path}."
            ) from exc

        # The PID is written for the operator's benefit only; the lock itself
        # is what guarantees exclusivity.
        handle.seek(0)
        handle.truncate()
        handle.write(str(os.getpid()))
        handle.flush()

        self._handle = handle

    def release(self) -> None:
        """Release the lock and close its handle."""

        handle = self._handle
        self._handle = None

        if handle is None:
            return

        try:
            self._unlock(handle)
        except OSError:
            # The lock is released by closing the handle regardless.
            pass
        finally:
            handle.close()

    @staticmethod
    def _lock_exclusive(handle) -> None:
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            return

        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

    @staticmethod
    def _unlock(handle) -> None:
        if os.name == "nt":
            import msvcrt

            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            return

        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def __enter__(self) -> "SingleInstanceLock":
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.release()
