"""The database backup and restore scripts in ``scripts/``.

``pg_dump`` and ``pg_restore`` are replaced by a stand-in that records how
it was called, so these tests need no PostgreSQL tools and touch no
database.
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest


SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import db_backup  # noqa: E402
import db_restore  # noqa: E402
import db_tools  # noqa: E402


TABLE_OF_CONTENTS = (
    "; Archive created at 2026-10-12\n"
    "215; 1259 16400 TABLE public product_listings vextro_app\n"
    "3501; 0 16400 TABLE DATA public product_listings vextro_app\n"
    "3502; 0 16411 TABLE DATA public price_history vextro_app\n"
)


class FakePostgresTools:
    """Stands in for ``pg_dump`` and ``pg_restore``."""

    def __init__(self, *, dump_fails=False, listing=TABLE_OF_CONTENTS, restore_fails=False):
        self.dump_fails = dump_fails
        self.listing = listing
        self.restore_fails = restore_fails
        self.calls: list[tuple[list[str], dict[str, str]]] = []

    def __call__(self, command, *, env, capture_output, text):
        self.calls.append((list(command), dict(env)))
        tool = Path(command[0]).stem

        if tool == "pg_dump":
            if self.dump_fails:
                return SimpleNamespace(returncode=1, stdout="", stderr="password authentication failed")
            Path(command[command.index("--file") + 1]).write_bytes(b"PGDMP archive")
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        if "--list" in command:
            if self.listing is None:
                return SimpleNamespace(returncode=1, stdout="", stderr="input file does not appear to be a valid archive")
            return SimpleNamespace(returncode=0, stdout=self.listing, stderr="")

        if self.restore_fails:
            return SimpleNamespace(returncode=1, stdout="", stderr="could not connect")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    def commands(self, tool):
        return [command for command, _ in self.calls if Path(command[0]).stem == tool]


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    """An env file naming a database, a backup directory, and fake tools."""

    env_file = tmp_path / ".env"
    env_file.write_text(
        "# local settings\n"
        "DB_HOST=127.0.0.1\n"
        "DB_PORT=5432\n"
        "DB_NAME=vextro_db\n"
        "DB_USER=vextro_app\n"
        'DB_PASSWORD="S3cret pass"\n',
        encoding="utf-8",
    )
    bin_dir = tmp_path / "pgbin"
    bin_dir.mkdir()
    suffix = ".exe" if sys.platform == "win32" else ""
    for tool in ("pg_dump", "pg_restore"):
        (bin_dir / f"{tool}{suffix}").write_bytes(b"")

    for name in ("DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD", "BACKUP_DIR", "BACKUP_KEEP", "PG_BIN_DIR"):
        monkeypatch.delenv(name, raising=False)

    backups = tmp_path / "backups"

    return SimpleNamespace(
        env_file=env_file,
        backups=backups,
        arguments=[
            "--env-file", str(env_file),
            "--backup-dir", str(backups),
            "--pg-bin", str(bin_dir),
        ],
    )


def history(workspace):
    return (workspace.backups / db_backup.HISTORY_FILE).read_text(encoding="utf-8")


# --------------------------------------------------------------------------
# Which database
# --------------------------------------------------------------------------


def test_the_database_is_the_one_the_api_is_configured_for(workspace):
    target = db_tools.database_target(db_tools.configuration(workspace.env_file, {}))

    assert (target.host, target.port, target.name, target.user) == (
        "127.0.0.1", "5432", "vextro_db", "vextro_app",
    )
    assert target.password == "S3cret pass"


def test_the_process_environment_overrides_the_env_file(workspace):
    values = db_tools.configuration(workspace.env_file, {"db_name": "vextro_test_db"})

    assert db_tools.database_target(values).name == "vextro_test_db"


def test_a_missing_password_is_an_error_not_a_default(tmp_path):
    with pytest.raises(db_tools.ConfigurationError):
        db_tools.database_target(db_tools.configuration(tmp_path / "absent.env", {}))


def test_a_tool_missing_from_the_directory_given_is_reported(tmp_path):
    with pytest.raises(db_tools.ConfigurationError):
        db_tools.find_tool("pg_dump", str(tmp_path))


# --------------------------------------------------------------------------
# Backing up
# --------------------------------------------------------------------------


def test_a_backup_is_written_verified_and_recorded(workspace, capsys):
    tools = FakePostgresTools()

    assert db_backup.main(workspace.arguments, run=tools) == 0

    backups = list(workspace.backups.glob("*.dump"))
    assert len(backups) == 1
    assert backups[0].name.startswith("vextro_db_")
    assert list(workspace.backups.glob("*.partial")) == []

    dump = tools.commands("pg_dump")[0]
    assert "--format=custom" in dump
    assert dump[-1] == "vextro_db"
    assert "-U" in dump and dump[dump.index("-U") + 1] == "vextro_app"
    assert len(tools.commands("pg_restore")) == 1          # the verification

    assert "OK vextro_db_" in history(workspace)
    assert "tables=2" in capsys.readouterr().out


def test_the_password_is_never_put_on_a_command_line(workspace):
    tools = FakePostgresTools()

    db_backup.main(workspace.arguments, run=tools)

    for command, environment in tools.calls:
        assert all("S3cret" not in part for part in command)
        assert environment["PGPASSWORD"] == "S3cret pass"


def test_a_failed_dump_leaves_no_file_and_reports_failure(workspace, capsys):
    tools = FakePostgresTools(dump_fails=True)

    assert db_backup.main(workspace.arguments, run=tools) == 1

    assert list(workspace.backups.glob("*.dump")) == []
    assert list(workspace.backups.glob("*.partial")) == []
    assert "FAILED" in history(workspace)
    assert "password authentication failed" in capsys.readouterr().err


def test_an_archive_that_cannot_be_read_back_is_not_kept(workspace):
    tools = FakePostgresTools(listing=None)

    assert db_backup.main(workspace.arguments, run=tools) == 1
    assert list(workspace.backups.glob("*.dump")) == []


def test_an_archive_without_table_data_is_not_a_backup(workspace):
    tools = FakePostgresTools(listing="; Archive created\n215; 1259 16400 TABLE public x y\n")

    assert db_backup.main(workspace.arguments, run=tools) == 1
    assert list(workspace.backups.glob("*.dump")) == []


# --------------------------------------------------------------------------
# Keeping only the recent ones
# --------------------------------------------------------------------------


def seed_backups(directory, *names):
    directory.mkdir(parents=True, exist_ok=True)
    for name in names:
        (directory / name).write_bytes(b"PGDMP")


def test_only_the_newest_backups_are_kept(workspace):
    seed_backups(
        workspace.backups,
        "vextro_db_20260101_020000.dump",
        "vextro_db_20260102_020000.dump",
        "vextro_db_20260103_020000.dump",
    )

    assert db_backup.main([*workspace.arguments, "--keep", "2"], run=FakePostgresTools()) == 0

    remaining = sorted(path.name for path in workspace.backups.glob("vextro_db_*.dump"))
    assert len(remaining) == 2
    assert remaining[0] == "vextro_db_20260103_020000.dump"
    assert "removed=2" in history(workspace)


def test_nothing_that_this_script_did_not_write_is_removed(workspace):
    seed_backups(
        workspace.backups,
        "vextro_db_20260101_020000.dump",
        "vextro_db_20260102_020000.dump",
        "vextro_test_db_20260101_020000.dump",              # another database
        "vextro_db_20260101_020000_before_restore.dump",    # a safety backup
        "vextro_db_from_munim.dump",                        # a colleague's dump
        "notes.txt",
    )

    db_backup.main([*workspace.arguments, "--keep", "1"], run=FakePostgresTools())

    names = {path.name for path in workspace.backups.iterdir()}
    assert {
        "vextro_test_db_20260101_020000.dump",
        "vextro_db_20260101_020000_before_restore.dump",
        "vextro_db_from_munim.dump",
        "notes.txt",
    } <= names
    assert "vextro_db_20260101_020000.dump" not in names
    assert "vextro_db_20260102_020000.dump" not in names


def test_a_failed_backup_never_removes_the_older_ones(workspace):
    seed_backups(
        workspace.backups,
        "vextro_db_20260101_020000.dump",
        "vextro_db_20260102_020000.dump",
    )

    db_backup.main([*workspace.arguments, "--keep", "1"], run=FakePostgresTools(dump_fails=True))

    assert len(list(workspace.backups.glob("vextro_db_*.dump"))) == 2


def test_backups_are_named_so_that_newest_sorts_first(tmp_path):
    seed_backups(
        tmp_path,
        db_backup.backup_name("vextro_db", datetime(2026, 9, 30, 23, 59, 59)),
        db_backup.backup_name("vextro_db", datetime(2026, 10, 1, 0, 0, 1)),
    )

    assert [path.name for path in db_backup.backups_of(tmp_path, "vextro_db")] == [
        "vextro_db_20261001_000001.dump",
        "vextro_db_20260930_235959.dump",
    ]


# --------------------------------------------------------------------------
# Restoring
# --------------------------------------------------------------------------


def test_a_restore_without_yes_changes_nothing(workspace, capsys):
    seed_backups(workspace.backups, "vextro_db_20260102_020000.dump")
    tools = FakePostgresTools()

    assert db_restore.main(workspace.arguments, run=tools) == 0

    assert tools.commands("pg_dump") == []
    assert all("--list" in command for command in tools.commands("pg_restore"))
    assert "Nothing was changed" in capsys.readouterr().out


def test_a_restore_saves_the_current_state_first_then_restores_the_newest(workspace):
    seed_backups(
        workspace.backups,
        "vextro_db_20260101_020000.dump",
        "vextro_db_20260102_020000.dump",
    )
    tools = FakePostgresTools()

    assert db_restore.main([*workspace.arguments, "--yes"], run=tools) == 0

    assert len(list(workspace.backups.glob("*_before_restore.dump"))) == 1

    restore = tools.commands("pg_restore")[-1]
    assert restore[-1].endswith("vextro_db_20260102_020000.dump")
    assert {"--clean", "--if-exists", "--no-owner", "--single-transaction"} <= set(restore)
    assert restore[restore.index("--dbname") + 1] == "vextro_db"

    order = [Path(command[0]).stem for command, _ in tools.calls]
    assert order.index("pg_dump") < len(order) - 1          # saved before restoring


def test_a_restore_with_no_backup_to_use_stops_before_touching_anything(workspace, capsys):
    tools = FakePostgresTools()

    assert db_restore.main([*workspace.arguments, "--yes"], run=tools) == 1
    assert tools.calls == []
    assert "No backup of vextro_db" in capsys.readouterr().err


def test_a_file_that_is_not_an_archive_is_refused(workspace):
    seed_backups(workspace.backups, "vextro_db_20260102_020000.dump")
    tools = FakePostgresTools(listing=None)

    assert db_restore.main([*workspace.arguments, "--yes"], run=tools) == 1
    assert tools.commands("pg_dump") == []
