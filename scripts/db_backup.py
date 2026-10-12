#!/usr/bin/env python3
"""Back up the VEXTRO database and keep the most recent copies.

    python scripts/db_backup.py
    python scripts/db_backup.py --keep 30 --backup-dir D:/vextro-backups

Meant to be run unattended by a scheduler (see
``scripts/install-backup-schedule.ps1`` and ``docs/deployment-and-demo.md``).

The database is the one the API uses, read from ``backend/.env``. The backup
is a ``pg_dump`` custom-format archive, the format ``pg_restore`` and the
team's restore instructions expect. It is written under a temporary name,
checked by asking ``pg_restore`` to list its contents, and only then given
its final name, so a file called ``*.dump`` is always a usable backup. Older
backups of the same database beyond ``--keep`` are then removed.

The exit code is 0 only when a verified backup was written. There is no
fallback that writes something else and reports success: a scheduler has to
be able to tell that a backup failed.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from db_tools import (
    DEFAULT_BACKUP_DIR,
    ENV_FILE,
    ConfigurationError,
    DatabaseTarget,
    configuration,
    database_target,
    find_tool,
)


DEFAULT_KEEP = 14
HISTORY_FILE = "backup_history.log"
STAMP = "%Y%m%d_%H%M%S"


class BackupError(RuntimeError):
    """No usable backup was produced."""


def backup_name(database: str, moment: datetime) -> str:
    return f"{database}_{moment.strftime(STAMP)}.dump"


def backups_of(backup_dir: Path, database: str) -> list[Path]:
    """Return this script's backups of one database, newest first.

    Matched by the exact name this script writes, so nothing else kept in
    the directory (a colleague's dump, another database's backups) is ever
    counted or removed.
    """

    pattern = re.compile(rf"{re.escape(database)}_\d{{8}}_\d{{6}}\.dump")

    return sorted(
        (
            path
            for path in backup_dir.glob(f"{database}_*.dump")
            if pattern.fullmatch(path.name)
        ),
        key=lambda path: path.name,
        reverse=True,
    )


def verify_backup(path: Path, target: DatabaseTarget, pg_restore: str, run) -> int:
    """Confirm an archive is readable and holds table data; return the count.

    ``pg_restore --list`` reads the archive's table of contents without
    touching any database. An archive it cannot read cannot be restored.
    """

    if not path.is_file() or path.stat().st_size == 0:
        raise BackupError("pg_dump wrote no data.")

    listing = run(
        [pg_restore, "--list", str(path)],
        env=target.environment(),
        capture_output=True,
        text=True,
    )

    if listing.returncode != 0:
        raise BackupError(
            f"The archive could not be read back: {listing.stderr.strip()[:300]}"
        )

    tables = sum(" TABLE DATA " in line for line in listing.stdout.splitlines())

    if tables == 0:
        raise BackupError("The archive holds no table data.")

    return tables


def create_backup(
    target: DatabaseTarget,
    backup_dir: Path,
    *,
    pg_dump: str,
    pg_restore: str,
    moment: datetime | None = None,
    name: str | None = None,
    run=subprocess.run,
) -> tuple[Path, int]:
    """Write one verified backup; return its path and its table count."""

    backup_dir.mkdir(parents=True, exist_ok=True)
    final = backup_dir / (name or backup_name(target.name, moment or datetime.now()))
    partial = final.with_name(final.name + ".partial")

    try:
        dump = run(
            [
                pg_dump,
                *target.connection_arguments(),
                "--format=custom",
                "--file",
                str(partial),
                target.name,
            ],
            env=target.environment(),
            capture_output=True,
            text=True,
        )

        if dump.returncode != 0:
            raise BackupError(f"pg_dump failed: {dump.stderr.strip()[:300]}")

        tables = verify_backup(partial, target, pg_restore, run)
        partial.replace(final)
    except BaseException:
        partial.unlink(missing_ok=True)
        raise

    return final, tables


def prune_backups(backup_dir: Path, database: str, keep: int) -> list[Path]:
    """Remove this database's backups beyond the newest ``keep``."""

    removed = backups_of(backup_dir, database)[max(1, keep):]

    for path in removed:
        path.unlink()

    return removed


def record(backup_dir: Path, message: str) -> None:
    """Append one line to the history a person can read afterwards."""

    backup_dir.mkdir(parents=True, exist_ok=True)

    with (backup_dir / HISTORY_FILE).open("a", encoding="utf-8") as history:
        history.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} {message}\n")


def main(argv: list[str] | None = None, *, run=subprocess.run) -> int:
    parser = argparse.ArgumentParser(
        description="Back up the VEXTRO database and keep the most recent copies.",
    )
    parser.add_argument("--backup-dir", help="where backups are kept (default: backups/, or BACKUP_DIR)")
    parser.add_argument("--keep", type=int, help=f"how many backups to keep (default: {DEFAULT_KEEP}, or BACKUP_KEEP)")
    parser.add_argument("--pg-bin", help="directory holding pg_dump and pg_restore (default: PATH, or PG_BIN_DIR)")
    parser.add_argument("--env-file", default=str(ENV_FILE), help="env file naming the database (default: backend/.env)")
    arguments = parser.parse_args(argv)

    values = configuration(Path(arguments.env_file))
    backup_dir = Path(
        arguments.backup_dir or values.get("BACKUP_DIR") or DEFAULT_BACKUP_DIR
    )

    try:
        keep = arguments.keep or int(values.get("BACKUP_KEEP") or DEFAULT_KEEP)
        bin_dir = arguments.pg_bin or values.get("PG_BIN_DIR") or None
        target = database_target(values)
        backup, tables = create_backup(
            target,
            backup_dir,
            pg_dump=find_tool("pg_dump", bin_dir),
            pg_restore=find_tool("pg_restore", bin_dir),
            run=run,
        )
    except (BackupError, ConfigurationError, OSError, ValueError) as error:
        print(f"Backup FAILED: {error}", file=sys.stderr)
        record(backup_dir, f"FAILED {error}")
        return 1

    removed = prune_backups(backup_dir, target.name, keep)
    size_mb = backup.stat().st_size / (1024 * 1024)
    summary = (
        f"OK {backup.name} database={target.name} tables={tables} "
        f"size={size_mb:.1f}MB kept={len(backups_of(backup_dir, target.name))} "
        f"removed={len(removed)}"
    )
    print(f"Backup {summary}")
    print(f"Stored in {backup_dir}")
    record(backup_dir, summary)

    return 0


if __name__ == "__main__":
    sys.exit(main())
