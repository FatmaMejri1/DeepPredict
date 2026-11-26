"""Angular browser journeys exercised through Django's test runner."""

import asyncio
import json
import os
import shutil
import socket
import subprocess
import tempfile
import time
import traceback
from datetime import datetime, timedelta, timezone
from contextlib import contextmanager
from functools import wraps
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from playwright.sync_api import sync_playwright

from accounts.models import Role
from infrastructure.models import Resource, ResourceType, Status
from ml_models.models import MLModelVersion, ModelType
from monitoring.models import Metric
from predictions.models import Prediction


User = get_user_model()
BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = BACKEND_DIR.parent
FRONTEND_DIR = PROJECT_DIR / "frontend"
EVIDENCE_DIR = BACKEND_DIR / "evidence" / "e2e"
ANGULAR_READY_TIMEOUT = 180


@contextmanager
def _django_sync_context(playwright_loop):
    """Hide Playwright's idle sync-loop marker during synchronous Django work.

    Playwright's sync API pumps its asyncio loop in a greenlet and leaves that
    loop marked as running on the calling thread between browser operations.
    Django's async-safety guard then mistakes synchronous ORM work on that same
    thread for async work. The loop is idle outside Playwright calls, so clear
    the marker only for Django's synchronous setup/teardown and restore it after.
    """
    running_loop = asyncio.events._get_running_loop()
    clear_marker = (
        playwright_loop is not None
        and running_loop is playwright_loop
    )
    if clear_marker:
        asyncio.events._set_running_loop(None)
    try:
        yield
    finally:
        if clear_marker:
            asyncio.events._set_running_loop(playwright_loop)


def _free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _record_scenario(test_method):
    @wraps(test_method)
    def wrapper(self):
        scenario = test_method.__name__.removeprefix("test_").replace("_", " ")
        started = datetime.now(timezone.utc)
        try:
            test_method(self)
        except Exception as exc:
            screenshot = None
            try:
                screenshot = self._screenshot(f"angular_error_{scenario.replace(' ', '_')}")
            except Exception:
                pass
            self.__class__.e2e_results.append({
                "scenario": scenario,
                "passed": False,
                "error": str(exc),
                "traceback": traceback.format_exc(),
                "started_at": started.isoformat(),
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "screenshots": [screenshot] if screenshot else [],
                "checks": self.e2e_checks,
            })
            self._write_report()
            raise
        else:
            self.__class__.e2e_results.append({
                "scenario": scenario,
                "passed": True,
                "error": "",
                "started_at": started.isoformat(),
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "screenshots": self.e2e_screenshots,
                "checks": self.e2e_checks,
            })
            self._write_report()

    return wrapper


class AngularDeepPredictE2ETests(StaticLiveServerTestCase):
    """Run the Angular frontend against Django's isolated live test database."""

    e2e_results = []
    playwright_loop = None

    @classmethod
    def setUpClass(cls):
        angular_cli = FRONTEND_DIR / "node_modules" / "@angular" / "cli" / "bin" / "ng.js"
        node = shutil.which("node")
        if not node or not angular_cli.exists():
            raise RuntimeError(
                "Angular E2E prerequisites are missing. Run `npm ci` in frontend/ "
                "and make sure Node.js is installed."
            )

        super().setUpClass()
        cls.e2e_results = []
        cls.playwright = None
        cls.playwright_loop = None
        cls.browser = None
        cls.angular_process = None
        cls.angular_log = None
        cls.proxy_config = None

        EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
        cls.angular_port = _free_port()
        proxy_file = tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", suffix=".json", delete=False
        )
        cls.proxy_config = Path(proxy_file.name)
        json.dump({
            "/api/**": {
                "target": cls.live_server_url,
                "secure": False,
                "changeOrigin": True,
            },
        }, proxy_file)
        proxy_file.close()

        cls.angular_log = tempfile.NamedTemporaryFile(
            mode="w+", encoding="utf-8", suffix=".log", delete=False
        )
        cls.angular_process = subprocess.Popen(
            [
                node,
                str(angular_cli),
                "serve",
                "--host",
                "127.0.0.1",
                "--port",
                str(cls.angular_port),
                "--proxy-config",
                str(cls.proxy_config),
            ],
            cwd=FRONTEND_DIR,
            stdout=cls.angular_log,
            stderr=subprocess.STDOUT,
            env={**os.environ, "CI": "true"},
        )

        try:
            cls._wait_for_angular()
            cls.playwright = sync_playwright().start()
            cls.playwright_loop = cls.playwright._loop
            cls.browser = cls.playwright.chromium.launch(headless=True)
        except Exception:
            if cls.browser:
                cls.browser.close()
            if cls.playwright:
                cls.playwright.stop()
            cls._stop_angular()
            cls._clear_playwright_loop_marker()
            raise

    @classmethod
    def _wait_for_angular(cls):
        url = f"http://127.0.0.1:{cls.angular_port}/"
        deadline = time.monotonic() + ANGULAR_READY_TIMEOUT
        while time.monotonic() < deadline:
            if cls.angular_process.poll() is not None:
                cls.angular_log.flush()
                cls.angular_log.seek(0)
                tail = "".join(cls.angular_log.readlines()[-60:])
                raise RuntimeError(f"Angular dev server exited during startup:\n{tail}")
            try:
                with urlopen(url, timeout=2) as response:
                    if response.status == 200 and b"app-root" in response.read():
                        return
            except (URLError, TimeoutError, OSError):
                pass
            time.sleep(1)

        cls.angular_log.flush()
        cls.angular_log.seek(0)
        tail = "".join(cls.angular_log.readlines()[-60:])
        raise RuntimeError(f"Angular dev server did not become ready:\n{tail}")

    @classmethod
    def _stop_angular(cls):
        if cls.angular_process and cls.angular_process.poll() is None:
            cls.angular_process.terminate()
            try:
                cls.angular_process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                cls.angular_process.kill()
                cls.angular_process.wait(timeout=5)
        if cls.angular_log:
            cls.angular_log.close()
            try:
                Path(cls.angular_log.name).unlink(missing_ok=True)
            except OSError:
                pass
        if cls.proxy_config:
            cls.proxy_config.unlink(missing_ok=True)

    @classmethod
    def tearDownClass(cls):
        try:
            if cls.browser:
                cls.browser.close()
        finally:
            try:
                if cls.playwright:
                    cls.playwright.stop()
            finally:
                try:
                    cls._stop_angular()
                finally:
                    cls._clear_playwright_loop_marker()
                    super().tearDownClass()

    @classmethod
    def _clear_playwright_loop_marker(cls):
        loop = cls.playwright_loop
        if loop is not None and asyncio.events._get_running_loop() is loop:
            asyncio.events._set_running_loop(None)
        cls.playwright_loop = None

    def setUp(self):
        with _django_sync_context(self.playwright_loop):
            super().setUp()
            self._create_demo_data()
        self.e2e_checks = []
        self.e2e_screenshots = []
        self.context = self.browser.new_context(
            viewport={"width": 1440, "height": 1000},
            device_scale_factor=1,
        )
        self.page = self.context.new_page()

    def tearDown(self):
        try:
            self.context.close()
        finally:
            with _django_sync_context(self.playwright_loop):
                super().tearDown()

    def _post_teardown(self):
        with _django_sync_context(self.playwright_loop):
            super()._post_teardown()

    def _create_demo_data(self):
        self.password = "E2E-Test-Password-2026!"
        self.it_pro = User.objects.create_user(
            username="e2e_itpro", email="e2e_itpro@example.com",
            password=self.password, role=Role.IT_PRO,
        )
        self.operator = User.objects.create_user(
            username="e2e_operator", email="e2e_operator@example.com",
            password=self.password, role=Role.OPERATOR,
        )
        self.sysadmin = User.objects.create_user(
            username="e2e_sysadmin", email="e2e_sysadmin@example.com",
            password=self.password, role=Role.SYSADMIN,
        )

        start = datetime(2026, 6, 1, tzinfo=timezone.utc)
        self.risk_model = MLModelVersion.objects.create(
            name="E2E Risk Model",
            model_type=ModelType.FAILURE_PREDICTION,
            architecture="GRU",
            version="e2e-v1",
            training_dataset="E2E fixture",
            trained_at=start,
            is_active=True,
            thresholds={"medium": 0.4, "high": 0.78, "critical": 0.88},
            evaluation_metrics={"protocol": "E2E fixture"},
        )
        self.anomaly_model = MLModelVersion.objects.create(
            name="E2E Anomaly Model",
            model_type=ModelType.ANOMALY_DETECTION,
            architecture="LSTM_AUTOENCODER",
            version="e2e-v1",
            training_dataset="E2E fixture",
            trained_at=start,
            is_active=True,
            thresholds={"anomaly": 1.2},
        )

        self.risk_drive = Resource.objects.create(
            name="E2E High Risk Drive",
            identifier="DP-E2E-RISK-001",
            resource_type=ResourceType.DISK,
            status=Status.HIGH_RISK,
            attributes={
                "model": "ST12000NM0008",
                "vendor": "Seagate",
                "datacenter": "E2E-DC",
                "capacity_bytes": 12_000_000_000_000,
            },
        )
        self.healthy_drive = Resource.objects.create(
            name="E2E Healthy Drive",
            identifier="DP-E2E-HEALTHY-001",
            resource_type=ResourceType.DISK,
            status=Status.HEALTHY,
            attributes={"model": "ST12000NM0008", "vendor": "Seagate", "datacenter": "E2E-DC"},
        )

        for offset in range(15):
            Metric.objects.create(
                resource=self.risk_drive,
                timestamp=start + timedelta(days=offset),
                values={
                    "smart_5_raw": offset * 2,
                    "smart_187_raw": 0,
                    "smart_197_raw": offset,
                },
            )

        Prediction.objects.create(
            resource=self.risk_drive,
            model_version=self.risk_model,
            score=0.865,
            risk_level="HIGH",
            horizon_days=7,
            window_start=start,
            window_end=start + timedelta(days=14),
        )
        Prediction.objects.create(
            resource=self.risk_drive,
            model_version=self.anomaly_model,
            score=1.6,
            is_anomalous=True,
            window_start=start,
            window_end=start + timedelta(days=14),
        )

    def _check(self, name, passed, detail=""):
        check = {"name": name, "passed": bool(passed), "detail": str(detail)}
        self.e2e_checks.append(check)
        self.assertTrue(passed, f"{name}: {detail}")

    def _screenshot(self, name):
        path = EVIDENCE_DIR / f"{name}.png"
        self.page.screenshot(path=str(path), full_page=True)
        stored_path = str(path.relative_to(PROJECT_DIR)).replace("\\", "/")
        if stored_path not in self.e2e_screenshots:
            self.e2e_screenshots.append(stored_path)
        return stored_path

    @classmethod
    def _write_report(cls):
        EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
        now = datetime.now(timezone.utc).isoformat()
        passed = sum(result["passed"] for result in cls.e2e_results)
        report = {
            "suite": "DeepPredict Angular E2E",
            "target": f"http://127.0.0.1:{cls.angular_port}",
            "run_at": now,
            "summary": {
                "total": len(cls.e2e_results),
                "passed": passed,
                "failed": len(cls.e2e_results) - passed,
            },
            "results": cls.e2e_results,
        }
        report_path = EVIDENCE_DIR / "angular_e2e_report.json"
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    def _login(self, username):
        self.page.goto(f"http://127.0.0.1:{self.angular_port}/login")
        self.page.get_by_label("Username").fill(username)
        self.page.get_by_label("Password").fill(self.password)
        self.page.get_by_role("button", name="Sign In").click()
        self.page.wait_for_url("**/overview", timeout=20_000)
        self.page.locator(".kpi-grid").wait_for(state="visible", timeout=20_000)

    @_record_scenario
    def test_it_pro_dashboard_drive_risk_and_charts(self):
        self._login("e2e_itpro")

        expected_kpis = {
            "TOTAL MONITORED DRIVES": "2",
            "HEALTHY": "1",
            "WARNING": "0",
            "HIGH RISK / CRITICAL": "1",
            "ANOMALOUS DRIVES": "1",
            "NOT SCORED": "1",
        }
        for label, expected in expected_kpis.items():
            card = self.page.locator(".kpi-card").filter(has_text=label)
            actual = card.locator(".kpi-value").inner_text()
            self._check(f"Dashboard KPI {label}", actual == expected, f"expected {expected}, got {actual}")

        self._screenshot("angular_01_itpro_overview")
        self.page.get_by_role("link", name="Drives Inventory").click()
        row = self.page.locator("tr").filter(has_text="DP-E2E-RISK-001")
        row.wait_for(state="visible")
        self._check("Drive list shows high-risk drive", row.get_by_text("HIGH", exact=True).count() == 1)
        self._screenshot("angular_02_drives_list")

        row.get_by_role("link", name="DP-E2E-RISK-001").click()
        self.page.locator(".drive-title").wait_for(state="visible")
        self._check("Drive detail shows selected serial", self.page.locator(".drive-title").inner_text() == "DP-E2E-RISK-001")
        self._check("Drive detail shows HIGH risk", self.page.locator(".assessment-card").first.get_by_text("HIGH", exact=True).count() == 1)

        canvases = self.page.locator(".charts-grid canvas")
        self.page.wait_for_function(
            """() => {
              const canvases = [...document.querySelectorAll('.charts-grid canvas')];
              if (canvases.length !== 2 || canvases.some((canvas) => canvas.width === 0 || canvas.height === 0)) {
                return false;
              }
              return canvases.every((canvas) => {
                const pixels = canvas.getContext('2d')?.getImageData(0, 0, canvas.width, canvas.height).data;
                return pixels && pixels.some((value, index) => index % 4 === 3 && value > 0);
              });
            }""",
            timeout=15_000,
        )
        rendered = canvases.evaluate_all(
            """els => els.every(canvas => {
              const ctx = canvas.getContext('2d');
              if (!ctx) return false;
              const pixels = ctx.getImageData(0, 0, canvas.width, canvas.height).data;
              for (let i = 3; i < pixels.length; i += 4) if (pixels[i] > 0) return true;
              return false;
            })"""
        )
        self._check("SMART and risk charts rendered", rendered, f"found {canvases.count()} canvases")
        self._screenshot("angular_03_drive_detail")

    @_record_scenario
    def test_operator_read_only_access(self):
        self._login("e2e_operator")
        admin_link = self.page.get_by_role("link", name="Users & Roles")
        self._check("Operator cannot see admin navigation", admin_link.count() == 0)
        self._check("Operator has no write actions on overview", self.page.get_by_role("link", name="Upload Telemetry").count() == 0)
        self._screenshot("angular_04_operator_overview")

        self.page.get_by_role("link", name="Drives Inventory").click()
        self.page.locator("tr").filter(has_text="DP-E2E-RISK-001").wait_for(state="visible")
        self.page.get_by_role("link", name="DP-E2E-RISK-001").click()
        self.page.locator(".drive-title").wait_for(state="visible")
        self._check("Operator cannot run a drive prediction", self.page.get_by_role("button", name="Run Prediction Now").count() == 0)

        denied_statuses = self.page.evaluate(
            """async () => {
              const token = localStorage.getItem('dp_access_token');
              const headers = {'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json'};
              const prediction = await fetch('/api/predictions/predict/', {
                method: 'POST', headers, body: '{}'
              });
              const predictionBody = await prediction.text();
              const upload = await fetch('/api/telemetry/upload/', {
                method: 'POST', headers, body: JSON.stringify({readings: []})
              });
              const uploadBody = await upload.text();
              return {
                prediction: prediction.status,
                predictionBody,
                upload: upload.status,
                uploadBody
              };
            }"""
        )
        self._check("Operator prediction API write is denied", denied_statuses["prediction"] == 403, denied_statuses)
        self._check("Operator telemetry upload API write is denied", denied_statuses["upload"] == 403, denied_statuses)
        self._screenshot("angular_05_operator_drive_detail")

    @_record_scenario
    def test_sysadmin_navigation_and_user_management(self):
        self._login("e2e_sysadmin")
        admin_link = self.page.get_by_role("link", name="Users & Roles")
        self._check("Sysadmin sees administration navigation", admin_link.count() == 1)
        self._screenshot("angular_06_sysadmin_overview")

        admin_link.click()
        self.page.get_by_role("heading", name="User Management").wait_for(state="visible")
        self.page.get_by_text("e2e_itpro", exact=True).wait_for(state="visible")
        self._check("Sysadmin can open user management", self.page.get_by_role("heading", name="User Management").count() == 1)
        for username in ("e2e_itpro", "e2e_operator", "e2e_sysadmin"):
            self._check(f"User management lists {username}", self.page.get_by_text(username, exact=True).count() >= 1)
        self._screenshot("angular_07_sysadmin_users")
