#!/usr/bin/env python3
"""Restore the VEXTRO database from a backup made by ``db_backup.py``.

    python scripts/db_restore.py                  # say what would be restored
    python scripts/db_restore.py --yes            # restore the newest backup
    python scripts/db_restore.py <file> --yes     # restore that backup

A restore replaces everything in the database named in ``backend/.env``.
So it does nothing without ``--yes``, and before it starts it takes a
backup of the database as it is now (named ``..._before_restore.dump``, and
never removed automatically), so the restore itself can be undone.

Stop the API first: it holds connections that make the restore wait.
Afterwards run ``alembic upgrade head`` in ``backend/``. A backup carries
the schema of the day it was taken, and migrations added since then are
missing until they are applied again.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from db_backup import STAMP, BackupError, backups_of, create_backup, verify_backup
from db_tools import (
    DEFAULT_BACKUP_DIR,
    ENV_FILE,
    ConfigurationError,
    configuration,
    database_target,
    find_tool,
)


def main(argv: list[str] | None = None, *, run=subprocess.run) -> int:
    parser = argparse.ArgumentParser(
        description="Restore the VEXTRO database from a backup.",
    )
    parser.add_argument("backup", nargs="?", help="backup file (default: the newest in the backup directory)")
    parser.add_argument("--yes", action="store_true", help="actually restore; without it nothing is changed")
    parser.add_argument("--no-safety-backup", action="store_true", help="do not back up the current database first")
    parser.add_argument("--backup-dir", help="where backups are kept (default: backups/, or BACKUP_DIR)")
    parser.add_argument("--pg-bin", help="directory holding pg_dump and pg_restore (default: PATH, or PG_BIN_DIR)")
    parser.add_argument("--env-file", default=str(ENV_FILE), help="env file naming the database (default: backend/.env)")
    arguments = parser.parse_args(argv)

    values = configuration(Path(arguments.env_file))
    backup_dir = Path(
        arguments.backup_dir or values.get("BACKUP_DIR") or DEFAULT_BACKUP_DIR
    )

    try:
        target = database_target(values)
        bin_dir = arguments.pg_bin or values.get("PG_BIN_DIR") or None
        pg_dump = find_tool("pg_dump", bin_dir)
        pg_restore = find_tool("pg_restore", bin_dir)

        if arguments.backup:
            backup = Path(arguments.backup)
        else:
            available = backups_of(backup_dir, target.name)
            if not available:
                raise BackupError(
                    f"No backup of {target.name} was found in {backup_dir}."
                )
            backup = available[0]

        tables = verify_backup(backup, target, pg_restore, run)
    except (BackupError, ConfigurationError, OSError) as error:
        print(f"Restore not started: {error}", file=sys.stderr)
        return 1

    print(f"Backup   : {backup} ({tables} tables)")
    print(f"Database : {target.name} on {target.host}:{target.port}")

    if not arguments.yes:
        print(
            "Nothing was changed. Everything in that database would be "
            "replaced; run again with --yes to do it."
        )
        return 0

    try:
        if not arguments.no_safety_backup:
            safety, _ = create_backup(
                target,
                backup_dir,
                pg_dump=pg_dump,
                pg_restore=pg_restore,
                name=(
                    f"{target.name}_{datetime.now().strftime(STAMP)}"
                    "_before_restore.dump"
                ),
                run=run,
            )
            print(f"Current state saved first: {safety.name}")

        # One transaction: the database ends up either fully restored or
        # exactly as it was, never half of each.
        restore = run(
            [
                pg_restore,
                *target.connection_arguments(),
                "--dbname",
                target.name,
                "--clean",
                "--if-exists",
                "--no-owner",
                "--no-privileges",
                "--single-transaction",
                str(backup),
            ],
            env=target.environment(),
            capture_output=True,
            text=True,
        )

        if restore.returncode != 0:
            raise BackupError(f"pg_restore failed: {restore.stderr.strip()[:400]}")
    except (BackupError, OSError) as error:
        print(f"Restore FAILED, the database was left as it was: {error}", file=sys.stderr)
        return 1

    print(f"Restored {target.name} from {backup.name}.")
    print("Now run `alembic upgrade head` in backend/ to apply newer migrations.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
