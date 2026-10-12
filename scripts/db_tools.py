"""What the database backup and restore scripts share.

Both read the database the API itself uses, from ``backend/.env``, so a
backup can never quietly be of some other database. Neither imports the
application: they must keep working when the application does not.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = REPOSITORY_ROOT / "backend" / ".env"
DEFAULT_BACKUP_DIR = REPOSITORY_ROOT / "backups"


class ConfigurationError(RuntimeError):
    """The database or the PostgreSQL tools could not be identified."""


def read_env_file(path: Path) -> dict[str, str]:
    """Return the ``KEY=value`` pairs of an env file; missing file, no pairs."""

    values: dict[str, str] = {}

    if not path.is_file():
        return values

    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip().removeprefix("export ").strip().upper()
        value = value.strip()

        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]

        if key:
            values[key] = value

    return values


def configuration(
    env_file: Path = ENV_FILE,
    environ: dict[str, str] | None = None,
) -> dict[str, str]:
    """Return the settings in force: the env file, overridden by the process."""

    process = os.environ if environ is None else environ
    values = read_env_file(env_file)
    values.update({key.upper(): value for key, value in process.items()})

    return values


@dataclass(frozen=True)
class DatabaseTarget:
    """One PostgreSQL database and the account that reaches it."""

    host: str
    port: str
    name: str
    user: str
    password: str

    def connection_arguments(self) -> list[str]:
        return ["-h", self.host, "-p", self.port, "-U", self.user]

    def environment(self) -> dict[str, str]:
        """The process environment for a PostgreSQL tool.

        The password travels here, never on the command line, where any
        other process on the machine could read it.
        """

        return {**os.environ, "PGPASSWORD": self.password}


def database_target(values: dict[str, str]) -> DatabaseTarget:
    """Return the database the API is configured to use."""

    password = values.get("DB_PASSWORD")

    if not password:
        raise ConfigurationError(
            "DB_PASSWORD is not set. The scripts read backend/.env, the same "
            "file the API uses."
        )

    return DatabaseTarget(
        host=values.get("DB_HOST") or "127.0.0.1",
        port=str(values.get("DB_PORT") or "5432"),
        name=values.get("DB_NAME") or "vextro_db",
        user=values.get("DB_USER") or "vextro_app",
        password=password,
    )


def _version_of(directory: Path) -> tuple[int, ...]:
    digits = "".join(
        character if character.isdigit() else " "
        for character in directory.parent.name
    ).split()

    return tuple(int(part) for part in digits) or (0,)


def find_tool(name: str, bin_dir: str | None = None) -> str:
    """Return the path of a PostgreSQL client tool such as ``pg_dump``.

    Looked for in the directory given (``PG_BIN_DIR`` or ``--pg-bin``),
    then on ``PATH``, then in the standard Windows install locations,
    newest version first.
    """

    executable = f"{name}.exe" if os.name == "nt" else name

    if bin_dir:
        candidate = Path(bin_dir) / executable
        if candidate.is_file():
            return str(candidate)
        raise ConfigurationError(
            f"{executable} was not found in {bin_dir}."
        )

    on_path = shutil.which(name)
    if on_path:
        return on_path

    installs = sorted(
        (
            directory
            for root in (
                os.environ.get("ProgramFiles"),
                os.environ.get("ProgramFiles(x86)"),
            )
            if root
            for directory in Path(root, "PostgreSQL").glob("*/bin")
            if (directory / executable).is_file()
        ),
        key=_version_of,
        reverse=True,
    )
    if installs:
        return str(installs[0] / executable)

    raise ConfigurationError(
        f"{executable} was not found. Add PostgreSQL's bin directory to PATH, "
        "or set PG_BIN_DIR in backend/.env, or pass --pg-bin."
    )
