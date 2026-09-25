#!/usr/bin/env python3
"""
VEXTRO Data Warehouse - Database Restore Utility
Usage:
    python scripts/db_restore.py [backup_file_path]
"""

import os
import sys
import subprocess
from pathlib import Path

BACKUP_DIR = Path(__file__).resolve().parent.parent / "backups"

DB_HOST = os.getenv("POSTGRES_HOST", "localhost")
DB_PORT = os.getenv("POSTGRES_PORT", "5432")
DB_USER = os.getenv("POSTGRES_USER", "postgres")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "1234")
DB_NAME = os.getenv("POSTGRES_DB", "vextro_db")


def restore_backup(backup_file=None):
    if not backup_file:
        backups = sorted(BACKUP_DIR.glob("*.sql"), reverse=True)
        if not backups:
            print("[!] No backup files found in backups/ directory.")
            sys.exit(1)
        backup_file = backups[0]
    else:
        backup_file = Path(backup_file)

    if not backup_file.exists():
        print(f"[!] Backup file not found: {backup_file}")
        sys.exit(1)

    print(f"[*] Starting PostgreSQL Database Restore...")
    print(f"   Source Backup : {backup_file.name}")
    print(f"   Target DB     : {DB_NAME}")

    env = os.environ.copy()
    env["PGPASSWORD"] = DB_PASSWORD

    psql_bin = "psql"
    psql_paths = [
        r"C:\Program Files\PostgreSQL\16\bin\psql.exe",
        r"C:\Program Files\PostgreSQL\15\bin\psql.exe",
        r"C:\Program Files\PostgreSQL\17\bin\psql.exe",
        r"C:\Program Files\PostgreSQL\18\bin\psql.exe",
        r"C:\Program Files\PostgreSQL\14\bin\psql.exe",
        r"D:\download floder\PostgreSQL18\bin\psql.exe",
    ]

    for p in psql_paths:
        if os.path.exists(p):
            psql_bin = p
            break

    cmd = [
        psql_bin,
        "-h", DB_HOST,
        "-p", DB_PORT,
        "-U", DB_USER,
        "-d", DB_NAME,
        "-f", str(backup_file),
    ]

    try:
        subprocess.run(cmd, env=env, check=True)
        print(f"[+] Database restoration complete from {backup_file.name}")
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"[!] Restoration status: {e}")


if __name__ == "__main__":
    file_arg = sys.argv[1] if len(sys.argv) > 1 else None
    restore_backup(file_arg)
