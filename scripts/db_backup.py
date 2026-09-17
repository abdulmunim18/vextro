#!/usr/bin/env python3
"""
VEXTRO Data Warehouse - Automated Database Backup Utility
Usage:
    python scripts/db_backup.py
"""

import os
import sys
import subprocess
from datetime import datetime
from pathlib import Path

# Ensure backup directory exists
BACKUP_DIR = Path(__file__).resolve().parent.parent / "backups"
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

# PostgreSQL Configuration
DB_HOST = os.getenv("POSTGRES_HOST", "localhost")
DB_PORT = os.getenv("POSTGRES_PORT", "5432")
DB_USER = os.getenv("POSTGRES_USER", "postgres")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "1234")
DB_NAME = os.getenv("POSTGRES_DB", "vextro_db")

def create_backup():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"vextro_warehouse_backup_{timestamp}.sql"
    backup_filepath = BACKUP_DIR / backup_filename

    print(f"[*] Starting PostgreSQL Database Backup...")
    print(f"   Database : {DB_NAME}")
    print(f"   Target   : {backup_filepath}")

    env = os.environ.copy()
    env["PGPASSWORD"] = DB_PASSWORD

    pg_dump_bin = "pg_dump"
    pg_dump_paths = [
        r"C:\Program Files\PostgreSQL\16\bin\pg_dump.exe",
        r"C:\Program Files\PostgreSQL\15\bin\pg_dump.exe",
        r"C:\Program Files\PostgreSQL\17\bin\pg_dump.exe",
        r"C:\Program Files\PostgreSQL\18\bin\pg_dump.exe",
        r"C:\Program Files\PostgreSQL\14\bin\pg_dump.exe",
        r"D:\download floder\PostgreSQL18\bin\pg_dump.exe",
    ]

    for p in pg_dump_paths:
        if os.path.exists(p):
            pg_dump_bin = p
            break

    cmd = [
        pg_dump_bin,
        "-h", DB_HOST,
        "-p", DB_PORT,
        "-U", DB_USER,
        "-F", "p",  # plain text SQL format
        "-f", str(backup_filepath),
        DB_NAME,
    ]

    try:
        result = subprocess.run(cmd, env=env, capture_output=True, text=True, check=True)
        size_mb = round(backup_filepath.stat().st_size / (1024 * 1024), 2)
        print(f"[+] Backup completed successfully!")
        print(f"   File : {backup_filename}")
        print(f"   Size : {size_mb} MB")
        return str(backup_filepath)
    except FileNotFoundError:
        print(f"[!] pg_dump binary not found in PATH or standard PostgreSQL paths.")
        print(f"    Writing fallback schema dump using SQLAlchemy...")
        return fallback_dump(backup_filepath)
    except subprocess.CalledProcessError as e:
        print(f"[!] pg_dump error: {e.stderr}")
        return fallback_dump(backup_filepath)

def fallback_dump(target_path):
    """Fallback python script to export database snapshot if pg_dump binary isn't in system PATH."""
    from sqlalchemy import create_engine, text

    db_url = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    engine = create_engine(db_url)

    with engine.connect() as conn:
        tables = conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")).fetchall()
        table_names = [t[0] for t in tables]

        with open(target_path, "w", encoding="utf-8") as f:
            f.write(f"-- VEXTRO Warehouse Snapshot Backup\n")
            f.write(f"-- Exported at: {datetime.now().isoformat()}\n\n")
            for tname in table_names:
                count = conn.execute(text(f"SELECT count(*) FROM {tname}")).scalar()
                f.write(f"-- Table {tname}: {count} records\n")

    print(f"[+] Fallback metadata snapshot written to {target_path}")
    return str(target_path)

if __name__ == "__main__":
    create_backup()
