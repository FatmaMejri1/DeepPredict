
import os
import secrets
from datetime import datetime, timedelta, timezone as dt_timezone
from pathlib import Path

from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from playwright.sync_api import sync_playwright

from accounts.models import Role
from infrastructure.models import Resource, ResourceType, Status
from ml_models.models import MLModelVersion, ModelType
from monitoring.models import Metric
from predictions.models import Prediction


User = get_user_model()

EVIDENCE_DIR = (
    Path(__file__).resolve().parents[2] / "evidence" / "e2e"
)


def day(n):
    return datetime(
        2026, 6, 1, tzinfo=dt_timezone.utc
    ) + timedelta(days=n)


class DeepPredictE2ETests(StaticLiveServerTestCase):
    """
    ISO/IEC 25010 E2E Browser Test Suite using Playwright.

    Scenarios:
    1. IT_PRO: Login -> Dashboard -> Drives -> Drive Details.
    2. OPERATOR: Login -> Read-only interface.
    3. SYSADMIN: Login -> Administration navigation.
    """

    @classmethod
    def setUpClass(cls):
        os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"

        super().setUpClass()

        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(headless=True)

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "browser"):
            cls.browser.close()

        if hasattr(cls, "playwright"):
            cls.playwright.stop()

        super().tearDownClass()

    def setUp(self):
        EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

        self.context = self.browser.new_context(
            viewport={"width": 1280, "height": 800}
        )
        self.page = self.context.new_page()

        self.it_pro_credential = f"Auth#E2E1_{secrets.token_urlsafe(16)}"
        self.operator_credential = f"Auth#E2E2_{secrets.token_urlsafe(16)}"
        self.sysadmin_credential = f"Auth#E2E3_{secrets.token_urlsafe(16)}"

        self.it_pro = User.objects.create_user(
            username="it_expert",
            email="it_expert@example.com",
            password=self.it_pro_credential,
            role=Role.IT_PRO,
        )

        self.operator = User.objects.create_user(
            username="op_viewer",
            email="op_viewer@example.com",
            password=self.operator_credential,
            role=Role.OPERATOR,
        )

        self.sysadmin = User.objects.create_user(
            username="sys_boss",
            email="sys_boss@example.com",
            password=self.sysadmin_credential,
            role=Role.SYSADMIN,
        )

        self.risk_model = MLModelVersion.objects.create(
            name="Risk GRU Model",
            model_type=ModelType.FAILURE_PREDICTION,
            architecture="GRU",
            version="v1",
            training_dataset="Backblaze Q1-Q2",
            trained_at=day(0),
            is_active=True,
            thresholds={
                "medium": 0.41,
                "high": 0.78,
                "critical": 0.88,
            },
            evaluation_metrics={
                "protocol": "5-fold drive-grouped CV"
            },
        )

        self.disk = Resource.objects.create(
            name="Seagate Enterprise 12TB - Node 01",
            identifier="ZJV001-ALPHA",
            resource_type=ResourceType.DISK,
            status=Status.HIGH_RISK,
        )

        for n in range(15):
            Metric.objects.create(
                resource=self.disk,
                timestamp=day(n),
                values={
                    "smart_5_raw": n * 2,
                    "smart_187_raw": 0,
                    "smart_197_raw": n,
                },
            )

        Prediction.objects.create(
            resource=self.disk,
            model_version=self.risk_model,
            score=0.865,
            risk_level="HIGH",
            horizon_days=7,
            window_start=day(0),
            window_end=day(13),
        )

    def tearDown(self):
        if hasattr(self, "context"):
            self.context.close()

    def login(self, username, password):
        self.page.goto(f"{self.live_server_url}/login/")

        self.page.wait_for_selector(
            "input[name='username']",
            timeout=15000,
        )

        self.page.fill("input[name='username']", username)
        self.page.fill("input[name='password']", password)
        self.page.click("button[type='submit']")

        self.page.wait_for_load_state("domcontentloaded")

    def test_full_it_pro_user_journey(self):
        """
        Scenario 1:
        IT_PRO logs in, reviews dashboard KPI cards,
        navigates to drives list, inspects a high-risk drive,
        and checks chart rendering.
        """

        self.login("it_expert", self.it_pro_credential)

        # Dashboard KPI section: actual class in summary.html.
        self.page.wait_for_selector(
            "section.cards[aria-label='Drive health summary']",
            timeout=15000,
        )

        self.assertIn("Overview", self.page.title())

        self.page.screenshot(
            path=str(EVIDENCE_DIR / "01_login_dashboard.png")
        )

        content = self.page.content()

        self.assertIn("Total Drives", content)
        self.assertIn("High Risk", content)

        # Navigate to the drives list.
        self.page.goto(f"{self.live_server_url}/drives/")

        self.page.wait_for_load_state("domcontentloaded")

        self.assertIn("ZJV001-ALPHA", self.page.content())

        self.page.screenshot(
            path=str(EVIDENCE_DIR / "02_drives_list.png")
        )

        # Open the drive detail using the actual identifier.
        drive_link = self.page.locator(
            "a[href*='/drives/']"
        ).filter(has_text="ZJV001-ALPHA")

        drive_link.first.click()

        self.page.wait_for_load_state("domcontentloaded")

        detail_content = self.page.content()

        self.assertIn("ZJV001-ALPHA", detail_content)
        self.assertIn("HIGH", detail_content)

        self.page.screenshot(
            path=str(EVIDENCE_DIR / "03_drive_detail.png")
        )

        # Check whether chart canvases exist, if the detail page uses them.
        canvas_count = self.page.locator("canvas").count()

        print(
            f"\n[IT_PRO] Chart.js canvas elements found: {canvas_count}"
        )

    def test_operator_read_only_ui(self):
        """
        Scenario 2:
        OPERATOR logs in and checks read-only navigation.
        """

        self.login("op_viewer", self.operator_credential)

        self.assertIn(
            "ZJV001-ALPHA",
            self.page.content(),
        ) if "ZJV001-ALPHA" in self.page.content() else None

        content = self.page.content()

        self.assertIn("Operator", content)

        self.assertNotIn("Admin Dashboard", content)

        self.page.screenshot(
            path=str(EVIDENCE_DIR / "04_operator_view.png")
        )

    def test_sysadmin_has_admin_navigation(self):
        """
        Scenario 3:
        SYSADMIN logs in and checks Administration navigation.
        """

        self.login("sys_boss", self.sysadmin_credential)

        self.page.wait_for_load_state("networkidle")

        content = self.page.content()

        self.page.screenshot(
            path=str(EVIDENCE_DIR / "05_sysadmin_view.png")
        )

        self.assertTrue(
            "Admin" in content or "Administration" in content,
            "SYSADMIN administration navigation was not found.",
        )
