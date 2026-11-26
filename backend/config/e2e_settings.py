"""Settings bootstrap used only by the isolated browser E2E entry point."""

import copy
import os
import tempfile
import uuid
from pathlib import Path

# Force the E2E settings module to construct SQLite settings before Django's
# connection handler is initialized; it must never inherit a PostgreSQL target.
os.environ["DB_ENGINE"] = "sqlite"

from .settings import *  # noqa: F403,E402


DATABASES = copy.deepcopy(DATABASES)  # noqa: F405
if DATABASES["default"]["ENGINE"] != "django.db.backends.sqlite3":
    raise RuntimeError("E2E bootstrap did not select SQLite.")

E2E_TEST_MODE = True
_is_full_regression_bootstrap = (
    os.environ.get("DJANGO_SETTINGS_MODULE") == "config.full_regression_settings"
)
E2E_TEST_DB_OWNER = (
    os.environ.get("DEEPPREDICT_FULL_REGRESSION_OWNER")
    if _is_full_regression_bootstrap
    else uuid.uuid4().hex
)
if not E2E_TEST_DB_OWNER:
    raise RuntimeError("Full-regression bootstrap owner is missing.")
E2E_TEST_TEMP_ROOT = Path(tempfile.gettempdir()).resolve(strict=False)
_directory_prefix = (
    "deeppredict-full-regression-"
    if _is_full_regression_bootstrap
    else "deeppredict-e2e-"
)
E2E_TEST_DB_DIRECTORY = E2E_TEST_TEMP_ROOT / f"{_directory_prefix}{E2E_TEST_DB_OWNER}"
E2E_TEST_DB_PATH = E2E_TEST_DB_DIRECTORY / "test.sqlite3"
DATABASES["default"].setdefault("TEST", {})["NAME"] = str(E2E_TEST_DB_PATH)
