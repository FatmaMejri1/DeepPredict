"""Guarded Django test runner with isolated file-backed SQLite bootstraps."""

import os
import sys
import threading
import time
from pathlib import Path

from django.conf import settings
from django.db import connections
from django.test.runner import DiscoverRunner

from config.test_database import validate_test_databases


LIVE_SERVER_SHUTDOWN_TIMEOUT = 30


class IsolatedDiscoverRunner(DiscoverRunner):
    def run_tests(self, test_labels, **kwargs):
        self._requested_test_labels = tuple(test_labels)
        if self._is_full_regression_run() and self._requested_test_labels:
            raise RuntimeError("Full-regression mode permits full test discovery only.")
        return super().run_tests(test_labels, **kwargs)

    def _is_e2e_run(self):
        return any(
            str(label).startswith("dashboard.test_e2e")
            for label in getattr(self, "_requested_test_labels", ())
        )

    def _is_full_regression_run(self):
        selected = os.environ.get("DJANGO_SETTINGS_MODULE") == "config.full_regression_settings"
        if not selected:
            return False
        if not getattr(settings, "FULL_REGRESSION_TEST_MODE", False):
            raise RuntimeError("Full-regression settings failed their mode assertion.")
        if os.environ.get("DEEPPREDICT_FULL_REGRESSION_OWNER") != settings.E2E_TEST_DB_OWNER:
            raise RuntimeError("Full-regression bootstrap owner is missing or mismatched.")
        return True

    def _uses_isolated_database(self):
        return self._is_e2e_run() or self._is_full_regression_run()

    def get_databases(self, suite):
        if self._uses_isolated_database():
            databases = self._get_databases(suite)
            # The E2E fixtures persist users, drives, metrics, models, and
            # predictions. Keep default registered even if a suite wrapper or
            # discovery path fails to propagate the test case's declaration.
            databases.setdefault("default", False)
            return databases
        return super().get_databases(suite)

    @staticmethod
    def _normalized_path(value):
        return Path(value).expanduser().resolve(strict=False)

    def _e2e_settings(self):
        full_regression = self._is_full_regression_run()
        expected_module = (
            "config.full_regression_settings" if full_regression else "config.e2e_settings"
        )
        expected_flag = (
            "FULL_REGRESSION_TEST_MODE" if full_regression else "E2E_TEST_MODE"
        )
        if os.environ.get("DJANGO_SETTINGS_MODULE") != expected_module or not getattr(
            settings, expected_flag, False
        ):
            raise RuntimeError(
                "This test path requires its dedicated pre-Django bootstrap."
            )
        if settings.DATABASES["default"]["ENGINE"] != "django.db.backends.sqlite3":
            raise RuntimeError("Isolated browser tests require dedicated SQLite settings.")
        if set(settings.DATABASES) != {"default"} or set(connections.settings) != {"default"}:
            raise RuntimeError("Isolated regression supports only the default database alias.")

        self._e2e_owner = settings.E2E_TEST_DB_OWNER
        self._e2e_directory = self._normalized_path(settings.E2E_TEST_DB_DIRECTORY)
        self._e2e_database = self._normalized_path(settings.E2E_TEST_DB_PATH)
        marker_name = (
            ".deeppredict-full-regression-owner"
            if full_regression
            else ".deeppredict-e2e-owner"
        )
        self._e2e_marker = self._e2e_directory / marker_name

        temp_root = self._normalized_path(settings.E2E_TEST_TEMP_ROOT)
        if self._e2e_directory.parent != temp_root:
            raise RuntimeError("E2E temporary database directory is outside the temp root.")
        directory_prefix = (
            "deeppredict-full-regression-" if full_regression else "deeppredict-e2e-"
        )
        if self._e2e_directory.name != f"{directory_prefix}{self._e2e_owner}":
            raise RuntimeError("Temporary directory does not match its run owner.")
        if self._e2e_database != self._e2e_directory / "test.sqlite3":
            raise RuntimeError("Temporary database path does not match its owned directory.")

        test_db_path = self._normalized_path(
            settings.BASE_DIR / "test_db.sqlite3"
        )
        if self._e2e_database == test_db_path:
            raise RuntimeError("Isolated database cannot target the standard test database.")
        if full_regression:
            evidence_directory = self._normalized_path(
                settings.FULL_REGRESSION_EVIDENCE_DIRECTORY
            )
            requested_evidence = os.environ.get("DEEPPREDICT_E2E_EVIDENCE_DIR")
            evidence_root = self._normalized_path(
                settings.BASE_DIR / "evidence" / "e2e"
            )
            expected_evidence = evidence_root / f"full-regression-{self._e2e_owner}"
            if (
                evidence_directory.parent != evidence_root
                or evidence_directory != expected_evidence
                or not requested_evidence
                or self._normalized_path(requested_evidence) != evidence_directory
            ):
                raise RuntimeError("Full-regression evidence path is not run-specific.")
            if evidence_directory.exists():
                raise RuntimeError("Full-regression evidence directory already exists.")
            intended_root = Path(settings.BASE_DIR) / "evidence" / "e2e"
            for component in (
                Path(settings.BASE_DIR) / "evidence",
                intended_root,
            ):
                if component.is_symlink():
                    raise RuntimeError(
                        "Full-regression evidence root contains a symlink; refusing setup."
                    )
                if component.exists() and not component.is_dir():
                    raise RuntimeError(
                        "Full-regression evidence root component is not a directory."
                    )
            if not intended_root.is_dir():
                raise RuntimeError("Full-regression evidence root is unavailable; refusing setup.")
            self._evidence_directory = evidence_directory

        configured_path = settings.DATABASES["default"].get("TEST", {}).get("NAME")
        if not configured_path or self._normalized_path(configured_path) != self._e2e_database:
            raise RuntimeError("Settings do not target the run-owned database path.")
        configured_application_path = self._normalized_path(
            settings.DATABASES["default"]["NAME"]
        )
        if full_regression and configured_application_path != self._e2e_database:
            raise RuntimeError("Full-regression settings do not select the run-owned database.")
        if not full_regression and configured_application_path == self._e2e_database:
            raise RuntimeError("E2E test target cannot be the configured application database.")

        # DiscoverRunner has already resolved aliases by this point. Validate
        # the exact cached handler config and wrapper Django will use.
        handler_config = connections.settings.get("default")
        if not handler_config:
            raise RuntimeError("Django's connection handler has no default database.")
        wrapper = connections["default"]
        effective_configs = (handler_config, wrapper.settings_dict)
        for config in effective_configs:
            if config.get("ENGINE") != "django.db.backends.sqlite3":
                raise RuntimeError("Django's effective database engine is not SQLite.")
            if full_regression and self._normalized_path(config.get("NAME")) != self._e2e_database:
                raise RuntimeError("Django's connection wrapper does not target the run-owned path.")
            effective_path = config.get("TEST", {}).get("NAME")
            if not effective_path or self._normalized_path(effective_path) != self._e2e_database:
                raise RuntimeError(
                    "Django's cached connection handler or wrapper does not resolve "
                    "to the run-owned temporary database. Refusing setup."
                )
        if wrapper.connection is not None:
            raise RuntimeError(
                "A database connection was opened before isolation was verified."
            )

        # setup_databases() validates after exclusive creation of the run-owned
        # directory and owner marker, immediately before Django setup.
        if self._e2e_database.exists() or self._e2e_directory.exists():
            raise RuntimeError("The unique temporary database path already exists.")

        return wrapper

    def _validate_test_database_config(self, databases, full_regression):
        if full_regression:
            validate_test_databases(
                databases,
                run_owned_sqlite_path=self._e2e_database,
                run_owner=self._e2e_owner,
            )
        else:
            validate_test_databases(databases)

    def _create_owned_e2e_directory(self):
        self._e2e_directory.mkdir(parents=False, exist_ok=False)
        self._e2e_directory_identity = self._file_identity(self._e2e_directory)
        with self._e2e_marker.open("x", encoding="utf-8") as marker:
            marker.write(self._e2e_owner)
        self._e2e_marker_identity = self._file_identity(self._e2e_marker)

    def _verify_e2e_ownership(self):
        if not self._e2e_directory or not self._e2e_database:
            raise RuntimeError("E2E database ownership was not initialized.")
        if self._e2e_directory.is_symlink():
            raise RuntimeError("E2E temporary directory became a symlink; refusing cleanup.")
        if self._normalized_path(self._e2e_database.parent) != self._e2e_directory:
            raise RuntimeError("E2E database escaped its owned temporary directory.")
        if (
            self._e2e_directory_identity is None
            or self._file_identity(self._e2e_directory) != self._e2e_directory_identity
        ):
            raise RuntimeError("E2E temporary directory identity changed; refusing cleanup.")
        try:
            owner = self._e2e_marker.read_text(encoding="utf-8")
        except OSError as exc:
            raise RuntimeError("E2E database ownership marker is unavailable.") from exc
        if owner != self._e2e_owner:
            raise RuntimeError("E2E database ownership marker does not match this run.")
        if (
            self._e2e_marker_identity is None
            or self._file_identity(self._e2e_marker) != self._e2e_marker_identity
        ):
            raise RuntimeError("E2E ownership marker identity changed; refusing cleanup.")

    def _wait_for_live_server(self):
        deadline = time.monotonic() + LIVE_SERVER_SHUTDOWN_TIMEOUT
        test_module = sys.modules.get("dashboard.test_e2e")
        test_class = getattr(test_module, "AngularDeepPredictE2ETests", None)
        server_threads = {
            thread for thread in threading.enumerate()
            if thread.name == "LiveServerThread"
        }
        server_thread = getattr(test_class, "server_thread", None)
        if server_thread is not None:
            server_threads.add(server_thread)
        for server_thread in server_threads:
            server_thread.join(timeout=max(0, deadline - time.monotonic()))
            if server_thread.is_alive():
                raise RuntimeError(
                    "A Django live-server thread did not stop within the cleanup timeout; "
                    "preserving the temporary database directory."
                )

    @staticmethod
    def _file_identity(path):
        stat = path.stat()
        return stat.st_dev, stat.st_ino

    def _remove_owned_database(self):
        self._verify_e2e_ownership()
        allowed_names = {
            self._e2e_database.name,
            f"{self._e2e_database.name}-journal",
            f"{self._e2e_database.name}-wal",
            f"{self._e2e_database.name}-shm",
            self._e2e_marker.name,
        }
        for entry in self._e2e_directory.iterdir():
            if entry.name not in allowed_names or entry.is_symlink() or not entry.is_file():
                raise RuntimeError(
                    "Unexpected content in E2E temporary directory; preserving it."
                )

        sidecar_identities = {}
        for suffix in ("-journal", "-wal", "-shm"):
            sidecar = Path(f"{self._e2e_database}{suffix}")
            if sidecar.exists():
                if sidecar.is_symlink() or not sidecar.is_file():
                    raise RuntimeError("Unexpected database sidecar; preserving directory.")
                sidecar_identities[sidecar] = self._file_identity(sidecar)

        # Complete ownership checks before the first deletion. The database
        # identity check immediately below is repeated at the unlink boundary.
        self._verify_e2e_ownership()
        if self._e2e_database.exists():
            if (
                self._e2e_database_identity is None
                or self._file_identity(self._e2e_database) != self._e2e_database_identity
            ):
                raise RuntimeError("E2E database identity changed; refusing deletion.")
            # Recheck immediately before unlinking the run-owned file.
            if self._file_identity(self._e2e_database) != self._e2e_database_identity:
                raise RuntimeError("E2E database identity changed before unlink.")
            # Path-based identity checks and unlink aren't atomic on Windows.
            # The remaining check-to-unlink race is constrained to this
            # exclusively created, owner-marked run directory; never recurse.
            self._e2e_database.unlink()
        for suffix in ("-journal", "-wal", "-shm"):
            sidecar = Path(f"{self._e2e_database}{suffix}")
            if sidecar.exists():
                expected_identity = sidecar_identities.get(sidecar)
                if expected_identity is None or self._file_identity(sidecar) != expected_identity:
                    raise RuntimeError("Database sidecar identity changed; refusing deletion.")
                self._verify_e2e_ownership()
                if self._file_identity(sidecar) != expected_identity:
                    raise RuntimeError("Database sidecar identity changed before unlink.")
                sidecar.unlink()
        if self._file_identity(self._e2e_marker) != self._e2e_marker_identity:
            raise RuntimeError("Ownership marker identity changed before unlink.")
        self._e2e_marker.unlink()
        if self._file_identity(self._e2e_directory) != self._e2e_directory_identity:
            raise RuntimeError("Temporary directory identity changed before removal.")
        self._e2e_directory.rmdir()

    def setup_databases(self, **kwargs):
        self._e2e_directory = None
        self._e2e_database = None
        self._e2e_marker = None
        self._e2e_owner = None
        self._e2e_database_identity = None
        self._e2e_directory_identity = None
        self._e2e_marker_identity = None
        self._e2e_application_name = None
        self._evidence_directory_identity = None

        if not self._uses_isolated_database():
            validate_test_databases(settings.DATABASES)
            return super().setup_databases(**kwargs)

        wrapper = self._e2e_settings()
        self._e2e_application_name = wrapper.settings_dict["NAME"]
        try:
            # Exclusive creation proves the directory was created by this run.
            self._create_owned_e2e_directory()
            if self._is_full_regression_run():
                self._evidence_directory.mkdir(parents=False, exist_ok=False)
                self._evidence_directory_identity = self._file_identity(self._evidence_directory)
            self._validate_test_database_config(settings.DATABASES, self._is_full_regression_run())
            self._validate_test_database_config(
                {"default": wrapper.settings_dict}, self._is_full_regression_run()
            )
            old_config = super().setup_databases(**kwargs)
            if not self._e2e_database.is_file():
                raise RuntimeError("Django did not create the run-owned E2E database.")
            self._e2e_database_identity = self._file_identity(self._e2e_database)
            return old_config
        except BaseException:
            try:
                connections.close_all()
                if self._e2e_directory.exists():
                    # A partially created database has no recorded identity;
                    # preserve it rather than inferring ownership after failure.
                    if not self._e2e_database.exists() or self._e2e_database_identity is not None:
                        self._remove_owned_database()
            except BaseException:
                # Fail closed and leave an uncertain temporary artifact intact.
                pass
            raise

    def teardown_databases(self, old_config, **kwargs):
        if not self._uses_isolated_database():
            return super().teardown_databases(old_config, **kwargs)

        self._verify_e2e_ownership()
        self._wait_for_live_server()
        if self._is_full_regression_run():
            if (
                not self._evidence_directory.is_dir()
                or self._evidence_directory.is_symlink()
                or self._evidence_directory_identity is None
                or self._file_identity(self._evidence_directory)
                != self._evidence_directory_identity
            ):
                raise RuntimeError(
                    "Run-specific evidence directory identity changed; preserving database."
                )

        wrapper = connections["default"]
        if self._e2e_database_identity is None or not self._e2e_database.exists():
            raise RuntimeError("Run-owned E2E database identity was not recorded.")
        if self._file_identity(self._e2e_database) != self._e2e_database_identity:
            raise RuntimeError("Run-owned E2E database identity changed before teardown.")
        effective_name = self._normalized_path(wrapper.settings_dict["NAME"])
        if effective_name != self._e2e_database:
            raise RuntimeError("Active wrapper no longer points at the owned E2E database.")

        # The server thread is stopped. Close wrappers before removing anything.
        connections.close_all()
        try:
            self._remove_owned_database()
        finally:
            # Django changed this wrapper to the test NAME during setup. Restore
            # its original configuration without opening a database connection.
            wrapper.settings_dict["NAME"] = self._e2e_application_name
