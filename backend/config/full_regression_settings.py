"""Settings for a full backend regression run in its own temporary SQLite DB."""

from .e2e_settings import *  # noqa: F403


E2E_TEST_MODE = False
FULL_REGRESSION_TEST_MODE = True
FULL_REGRESSION_EVIDENCE_DIRECTORY = (
    BASE_DIR / "evidence" / "e2e" / f"full-regression-{E2E_TEST_DB_OWNER}"
)

# Both the application NAME and Django's test NAME identify the isolated run
# target. This prevents even the pre-setup wrapper from naming db.sqlite3.
DATABASES["default"]["NAME"] = str(E2E_TEST_DB_PATH)

# The existing test runner still recognizes the default alias and the exact
# run-owned temporary database configured by e2e_settings before Django setup.
if DATABASES["default"]["ENGINE"] != "django.db.backends.sqlite3":
    raise RuntimeError("Full regression requires SQLite.")
if DATABASES["default"].get("TEST", {}).get("NAME") != str(E2E_TEST_DB_PATH):
    raise RuntimeError("Full-regression database target is not the run-owned path.")
