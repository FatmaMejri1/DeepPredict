import json
from datetime import datetime, timedelta, timezone as dt_timezone

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from infrastructure.models import Resource, ResourceType, Status
from ml_models.models import MLModelVersion, ModelType
from monitoring.models import Metric
from predictions.models import Prediction

User = get_user_model()


def day(n):
    return datetime(2026, 6, 1, tzinfo=dt_timezone.utc) + timedelta(days=n)


class DashboardTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user("ana", "ana@example.com", "pw-12345-xyz")
        cls.risk_v = MLModelVersion.objects.create(
            name="Disk failure risk", model_type=ModelType.FAILURE_PREDICTION, architecture="GRU",
            version="v1", training_dataset="test", trained_at=day(0), is_active=True,
            thresholds={"medium": 0.4, "high": 0.78, "critical": 0.88},
            evaluation_metrics={"protocol": "test protocol", "results": {
                "medium": {"healthy_drives_flagged": 0.03, "failed_drives_detected": 0.75},
                "high": {"healthy_drives_flagged": 0.01, "failed_drives_detected": 0.55}}})
        cls.ano_v = MLModelVersion.objects.create(
            name="Disk anomaly", model_type=ModelType.ANOMALY_DETECTION, architecture="LSTM_AUTOENCODER",
            version="v1", training_dataset="test", trained_at=day(0), is_active=True,
            thresholds={"anomaly": 1.6},
            evaluation_metrics={"protocol": "p", "results": {
                "healthy_drives_flagged": 0.01, "failed_drives_detected": 0.14}})

        cls.bad = Resource.objects.create(name="Disk AAA", identifier="AAA111", resource_type=ResourceType.DISK,
                                          status=Status.HIGH_RISK, attributes={"demo_failed_on": "2026-06-20"})
        cls.ok = Resource.objects.create(name="Disk BBB", identifier="BBB222", resource_type=ResourceType.DISK,
                                         status=Status.HEALTHY)
        cls.new = Resource.objects.create(name="Disk CCC", identifier="CCC333", resource_type=ResourceType.DISK,
                                          status=Status.HEALTHY)
        for r in (cls.bad, cls.ok):
            for n in range(20):
                Metric.objects.create(resource=r, timestamp=day(n), values={"smart_5_raw": n, "smart_187_raw": None})
        for n, (res, level, score, anom) in enumerate([
                (cls.bad, "LOW", 0.1, False), (cls.bad, "HIGH", 0.85, True), (cls.ok, "LOW", 0.02, False)]):
            Prediction.objects.create(resource=res, model_version=cls.risk_v, score=score, horizon_days=7,
                                      risk_level=level, window_start=day(n), window_end=day(n + 13))
            Prediction.objects.create(resource=res, model_version=cls.ano_v, score=score * 2, is_anomalous=anom,
                                      window_start=day(n), window_end=day(n + 13))

    def login(self):
        self.client.login(username="ana", password="pw-12345-xyz")

    def test_pages_require_login(self):
        for name in ("summary", "resources", "models"):
            response = self.client.get(reverse(f"dashboard:{name}"))
            self.assertEqual(response.status_code, 302)
            self.assertIn("/login/", response["Location"])
        response = self.client.get(reverse("dashboard:resource_detail", args=[self.bad.pk]))
        self.assertEqual(response.status_code, 302)

    def test_login_and_logout(self):
        response = self.client.post(reverse("dashboard:login"), {"username": "ana", "password": "pw-12345-xyz"})
        self.assertRedirects(response, reverse("dashboard:summary"))
        response = self.client.post(reverse("dashboard:logout"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.get(reverse("dashboard:summary")).status_code, 302)

    def test_wrong_password_shows_error(self):
        response = self.client.post(reverse("dashboard:login"), {"username": "ana", "password": "nope"})
        self.assertContains(response, "Wrong username or password")

    def test_summary_counts(self):
        self.login()
        response = self.client.get(reverse("dashboard:summary"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total"], 3)
        self.assertEqual(response.context["high_risk"], 1)
        self.assertEqual(response.context["healthy"], 2)
        self.assertEqual(response.context["anomalous"], 1)
        self.assertEqual(response.context["not_scored"], 1)
        self.assertEqual(response.context["top"][0].identifier, "AAA111")      # highest risk first
        self.assertContains(response, "AAA111")

    def test_latest_prediction_wins(self):
        self.login()
        response = self.client.get(reverse("dashboard:resources"))
        drive = [d for d in response.context["page_obj"] if d.identifier == "AAA111"][0]
        self.assertEqual(drive.risk_level, "HIGH")                              # not the older LOW one
        self.assertTrue(drive.is_anomalous)

    def test_list_filter_search_and_sort(self):
        self.login()
        url = reverse("dashboard:resources")
        ids = lambda r: [d.identifier for d in r.context["page_obj"]]
        self.assertEqual(ids(self.client.get(url, {"status": "HIGH_RISK"})), ["AAA111"])
        self.assertEqual(ids(self.client.get(url, {"q": "bbb"})), ["BBB222"])
        self.assertEqual(ids(self.client.get(url, {"sort": "name"})), ["AAA111", "BBB222", "CCC333"])
        self.assertEqual(ids(self.client.get(url))[-1], "CCC333")               # not scored goes last
        self.assertEqual(self.client.get(url, {"status": "nonsense", "sort": "x", "page": "abc"}).status_code, 200)

    def test_detail_has_chart_data(self):
        self.login()
        response = self.client.get(reverse("dashboard:resource_detail", args=[self.bad.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "AAA111")
        self.assertContains(response, "2026-06-20")                             # demo information
        chart = response.context["chart"]
        self.assertEqual(len(chart["smart"]["labels"]), 20)
        self.assertEqual(len(chart["risk"]["scores"]), 2)
        self.assertEqual(chart["thresholds"]["high"], 0.78)
        content = response.content.decode()
        start = content.index('id="chart-data"')
        payload = content[content.index(">", start) + 1: content.index("</script>", start)]
        self.assertIn("risk", json.loads(payload))

    def test_detail_of_unscored_drive(self):
        self.login()
        response = self.client.get(reverse("dashboard:resource_detail", args=[self.new.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No predictions yet")

    def test_unknown_drive_is_404(self):
        self.login()
        response = self.client.get(reverse("dashboard:resource_detail", args=["00000000-0000-0000-0000-000000000000"]))
        self.assertEqual(response.status_code, 404)

    def test_models_page(self):
        self.login()
        response = self.client.get(reverse("dashboard:models"))
        self.assertContains(response, "Disk failure risk")
        self.assertContains(response, "Disk anomaly")
        self.assertContains(response, "test protocol")
        self.assertContains(response, "not a probability")
