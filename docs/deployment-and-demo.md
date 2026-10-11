# VEXTRO Deployment and Demo Reliability

## Docker startup

1. Copy `.env.docker.example` to `.env.docker` and replace every secret.
2. Build and start the stack:

   ```powershell
   docker compose --env-file .env.docker up --build -d
   ```

3. Open `http://localhost:8080` and verify:

   ```powershell
   Invoke-RestMethod http://localhost:8080/api/v1/health
   Invoke-RestMethod http://localhost:8080/api/v1/database/health
   ```

The backend container applies Alembic migrations before starting. PostgreSQL data is stored in the named `vextro_postgres_data` volume.

## Safe shutdown and backup

Stop services without deleting database data:

```powershell
docker compose --env-file .env.docker down
```

Create a logical backup:

```powershell
docker compose --env-file .env.docker exec -T db pg_dump -U vextro_app -d vextro_db > vextro-backup.sql
```

Do not use `down -v` unless the named database volume is intentionally being deleted and a verified backup exists.

## Scheduled database backups

`scripts/db_backup.py` backs up the database the API uses (read from `backend/.env`) to `backups/`:

```powershell
python scripts\db_backup.py
```

What one run does:

1. Writes a `pg_dump` custom-format archive under a temporary name.
2. Asks `pg_restore` to list the archive. An archive that cannot be read back, or that holds no table data, is deleted and the run fails.
3. Gives the archive its final name, `<database>_<date>_<time>.dump`.
4. Removes this database's older backups beyond the newest 14 (`--keep`, or `BACKUP_KEEP`). Files it did not write are never touched.
5. Appends one line to `backups/backup_history.log`.

The exit code is 0 only when a verified backup exists, so a scheduler can tell a failure from a success. The password is passed in the process environment, never on the command line.

Schedule it once per machine.

Windows (Task Scheduler, daily, and as soon as the machine is next on if it was off at that time):

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install-backup-schedule.ps1 -At 13:00 -Keep 14
```

`-Remove` deletes the schedule and leaves the backups. `-WhatIf` shows what would be registered.

Linux (cron, 02:00 daily):

```bash
0 2 * * * cd /path/to/vextro && backend/.venv/bin/python scripts/db_backup.py >> backups/cron.log 2>&1
```

Optional settings, in `backend/.env` or the environment:

| Setting | Meaning | Default |
|---|---|---|
| `PG_BIN_DIR` | Directory holding `pg_dump` and `pg_restore` | `PATH`, then `Program Files\PostgreSQL\*\bin` |
| `BACKUP_DIR` | Where backups are kept | `backups/` |
| `BACKUP_KEEP` | How many backups to keep | 14 |

### Restoring

```powershell
python scripts\db_restore.py            # says which backup and which database, changes nothing
python scripts\db_restore.py --yes      # restores the newest backup
```

A restore replaces everything in the database. It first saves the current state as `..._before_restore.dump`, runs in one transaction so a failure leaves the database as it was, and reminds you to run `alembic upgrade head` afterwards. Stop the API before restoring.

A restore drill is the only proof a backup works: `DB_NAME=vextro_test_db python scripts/db_restore.py <file> --yes --no-safety-backup` restores into the test database, which the test suite rebuilds on its next run.

## Demo fallback modes

- Marketplace unavailable: use saved fixtures and seeded catalog data.
- Internet unavailable: run the Docker stack locally.
- AI dependency unavailable: the assistant returns deterministic database-grounded catalog, comparison, price-history and rule-based buy/wait responses.
- Limited price history: the UI shows low confidence and observation coverage instead of claiming a reliable forecast.
- Deployment unavailable: use local backend and frontend startup documented in the root README.

## Final demo sequence

1. Search and filter products by platform, price, rating and availability.
2. Compare two products and show normalized specifications and offers.
3. Open buy/wait guidance and explain confidence/data coverage.
4. Create a price alert and demonstrate an in-app notification.
5. Ask the assistant for a grounded comparison and follow-up price history.
6. Open the SME workspace, competitor risk metrics and PDF/Excel exports.
7. Run dynamic pricing scenarios and explain that they are advisory only.
