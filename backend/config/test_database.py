"""Safety checks for Django's test database configuration."""

import re
import tempfile
from pathlib import Path


PROTECTED_DATABASE_NAMES = {"deeppredict_benchmark"}


def _test_database_name(database):
    configured_name = database.get("TEST", {}).get("NAME")
    if configured_name:
        return configured_name

    name = database["NAME"]
    if database["ENGINE"].endswith("sqlite3"):
        path = Path(name)
        return path.with_name(f"test_{path.name}")
    return f"test_{name}"


def _normal_name(value):
    return str(value).strip().casefold()


def _sqlite_path(value):
    return Path(value).expanduser().resolve(strict=False)


def _validate_run_owned_sqlite_target(database, test_name, owned_path, run_owner):
    """Validate the narrowly permitted full-regression SQLite target."""
    if not run_owner or re.fullmatch(r"[0-9a-f]{32}", str(run_owner)) is None:
        raise RuntimeError("A valid full-regression owner is required for this allowance.")
    if not owned_path or not database["ENGINE"].endswith("sqlite3"):
        raise RuntimeError("The run-owned allowance is valid only for SQLite.")

    temp_root = _sqlite_path(tempfile.gettempdir())
    expected_directory = temp_root / f"deeppredict-full-regression-{run_owner}"
    expected_path = expected_directory / "test.sqlite3"
    supplied_path = _sqlite_path(owned_path)
    application_path = _sqlite_path(database["NAME"])
    test_path = _sqlite_path(test_name)
    marker = expected_directory / ".deeppredict-full-regression-owner"

    if (
        supplied_path != expected_path
        or application_path != expected_path
        or test_path != expected_path
    ):
        raise RuntimeError("Run-owned allowance requires exact application/test path agreement.")
    if expected_directory.is_symlink() or not expected_directory.is_dir():
        raise RuntimeError("Run-owned temporary directory is unavailable or unsafe.")
    if expected_path.exists():
        raise RuntimeError("Run-owned SQLite target already exists; refusing reuse.")
    if marker.is_symlink() or not marker.is_file():
        raise RuntimeError("Run-owned temporary directory has no valid owner marker.")
    try:
        if marker.read_text(encoding="utf-8") != run_owner:
            raise RuntimeError("Run-owned temporary directory owner marker mismatches.")
    except OSError as exc:
        raise RuntimeError("Run-owned temporary directory owner marker is unreadable.") from exc
    if {entry.name for entry in expected_directory.iterdir()} != {marker.name}:
        raise RuntimeError("Run-owned temporary directory is not exclusively initialized.")


def validate_test_databases(databases, *, run_owned_sqlite_path=None, run_owner=None):
    """Reject test database targets that overlap application or protected DBs."""
    if run_owned_sqlite_path is not None and run_owner is None:
        raise RuntimeError("Run-owned database allowance requires an owner marker.")
    for alias, database in databases.items():
        test_name = _test_database_name(database)
        engine = database["ENGINE"]
        if run_owned_sqlite_path is not None and not engine.endswith("sqlite3"):
            raise RuntimeError("Run-owned database allowance is restricted to SQLite.")

        if engine.endswith("sqlite3"):
            test_path = _sqlite_path(test_name)
            application_path = _sqlite_path(database["NAME"])
            if run_owned_sqlite_path is not None:
                _validate_run_owned_sqlite_target(
                    database, test_name, run_owned_sqlite_path, run_owner
                )
            elif test_path == application_path:
                raise RuntimeError(
                    f"Refusing test setup: database alias '{alias}' resolves its "
                    "test database to the application SQLite database."
                )

            candidate_names = {
                _normal_name(test_path.name),
                _normal_name(test_path.stem),
            }
        else:
            normalized_test_name = _normal_name(test_name)
            if normalized_test_name == _normal_name(database["NAME"]):
                raise RuntimeError(
                    f"Refusing test setup: database alias '{alias}' resolves its "
                    "test database to the application database."
                )
            candidate_names = {normalized_test_name}

        if candidate_names & PROTECTED_DATABASE_NAMES:
            raise RuntimeError(
                f"Refusing test setup: database alias '{alias}' targets a "
                "protected database name."
            )
