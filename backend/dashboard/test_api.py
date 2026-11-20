from datetime import datetime, timezone
import uuid
from unittest.mock import MagicMock, patch
from urllib.error import URLError

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import Role
from audit.models import ActionType, AuditLog
from infrastructure.models import Resource, ResourceType, Status
from ml_models.models import MLModelVersion, ModelType
from monitoring.models import Metric
from predictions.models import Prediction, RiskLevel
from dashboard.services import inference_service_health

User = get_user_model()


class DashboardAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.sysadmin = User.objects.create_user(
            username="admin", email="admin@example.com", password="password123", role=Role.SYSADMIN
        )
        self.operator = User.objects.create_user(
            username="operator", email="op@example.com", password="password123", role=Role.OPERATOR
        )
        self.it_pro = User.objects.create_user(
            username="itpro", email="it@example.com", password="password123", role=Role.IT_PRO
        )

        self.disk = Resource.objects.create(
            name="Disk 1",
            identifier="ZJV001",
            resource_type=ResourceType.DISK,
            attributes={"model": "ST12000NM0007", "vendor": "Seagate", "datacenter": "DC-1"},
            status=Status.HEALTHY,
        )

        self.risk_model = MLModelVersion.objects.create(
            name="RiskGRU",
            model_type=ModelType.FAILURE_PREDICTION,
            architecture="GRU",
            version="1.0.0",
            training_dataset="backblaze_2026",
            trained_at=datetime.now(timezone.utc),
            thresholds={"medium": 0.35, "high": 0.60, "critical": 0.80},
            is_active=True,
        )

        self.ano_model = MLModelVersion.objects.create(
            name="AnomalyLSTM",
            model_type=ModelType.ANOMALY_DETECTION,
            architecture="LSTM_AUTOENCODER",
            version="1.0.0",
            training_dataset="backblaze_2026",
            trained_at=datetime.now(timezone.utc),
            thresholds={"anomaly": 0.05},
            is_active=True,
        )

        now = datetime.now(timezone.utc)
        self.metric = Metric.objects.create(
            resource=self.disk,
            timestamp=now,
            values={"smart_5_raw": 0.0, "smart_187_raw": 0.0, "smart_197_raw": 0.0},
        )

        Prediction.objects.create(
            resource=self.disk,
            model_version=self.risk_model,
            score=0.15,
            risk_level=RiskLevel.LOW,
            horizon_days=7,
            window_start=now,
            window_end=now,
        )

    def test_summary_api_authenticated(self):
        self.client.force_authenticate(user=self.operator)
        resp = self.client.get("/api/dashboard/summary/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("total", resp.data)
        self.assertIn("healthy", resp.data)
        self.assertIn("top_critical", resp.data)

    def test_summary_api_unauthenticated_fails(self):
        resp = self.client.get("/api/dashboard/summary/")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_dashboard_activity_api_authenticated(self):
        Prediction.objects.create(
            resource=self.disk,
            model_version=self.ano_model,
            score=1.4,
            is_anomalous=True,
            window_start=self.metric.timestamp,
            window_end=self.metric.timestamp,
        )
        self.client.force_authenticate(user=self.operator)

        resp = self.client.get("/api/dashboard/activity/")

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data["results"]), 2)
        anomaly = next(item for item in resp.data["results"] if item["kind"] == "Anomaly detection")
        self.assertEqual(anomaly["drive_identifier"], self.disk.identifier)
        self.assertEqual(anomaly["outcome"], "Anomaly detected")
        self.assertIn("created_at", anomaly)

    def test_dashboard_activity_api_unauthenticated_fails(self):
        resp = self.client.get("/api/dashboard/activity/")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch("dashboard.api_views.inference_service_health")
    def test_dashboard_health_api_authenticated(self, health_check):
        health_check.return_value = {
            "status": "online",
            "model_version": "gru-lstm-v1",
            "checked_at": "2026-11-20T12:00:00+00:00",
        }
        self.client.force_authenticate(user=self.operator)

        resp = self.client.get("/api/dashboard/health/")

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["status"], "online")
        self.assertEqual(resp.data["model_version"], "gru-lstm-v1")

    def test_dashboard_health_api_unauthenticated_fails(self):
        resp = self.client.get("/api/dashboard/health/")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_drives_list_and_filter(self):
        self.client.force_authenticate(user=self.operator)
        resp = self.client.get("/api/drives/?search=ZJV001")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["count"], 1)
        self.assertEqual(resp.data["results"][0]["identifier"], "ZJV001")

    def test_drive_detail_and_telemetry(self):
        self.client.force_authenticate(user=self.operator)
        detail_resp = self.client.get(f"/api/drives/{self.disk.id}/")
        self.assertEqual(detail_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_resp.data["identifier"], "ZJV001")

        telem_resp = self.client.get(f"/api/drives/{self.disk.id}/telemetry/")
        self.assertEqual(telem_resp.status_code, status.HTTP_200_OK)
        self.assertIn("smart", telem_resp.data)
        self.assertIn("risk", telem_resp.data)

    def test_ml_models_list(self):
        self.client.force_authenticate(user=self.operator)
        resp = self.client.get("/api/ml-models/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 2)

    def test_telemetry_upload_permission(self):
        # Operator cannot upload (requires IT_PRO or SYSADMIN)
        self.client.force_authenticate(user=self.operator)
        resp = self.client.post("/api/telemetry/upload/", {"readings": []}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

        # IT_PRO can upload
        self.client.force_authenticate(user=self.it_pro)
        resp = self.client.post(
            "/api/telemetry/upload/",
            {
                "readings": [
                    {
                        "serial_number": "ZJV001",
                        "date": "2026-11-01",
                        "smart_5_raw": 10,
                    }
                ]
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["status"], "success")
        upload_log = AuditLog.objects.get(action=ActionType.TELEMETRY_UPLOAD)
        self.assertEqual(upload_log.user, self.it_pro)
        self.assertEqual(upload_log.resource_type, "Telemetry")
        self.assertEqual(upload_log.details["readings_count"], 1)


class InferenceServiceHealthTests(TestCase):
    @patch("dashboard.services.urlopen")
    def test_health_check_reports_online_model(self, mocked_urlopen):
        response = MagicMock()
        response.status = 200
        response.read.return_value = b'{"status":"ok","model_version":"gru-lstm-v1"}'
        response.__enter__.return_value = response
        mocked_urlopen.return_value = response

        result = inference_service_health()

        self.assertEqual(result["status"], "online")
        self.assertEqual(result["model_version"], "gru-lstm-v1")
        self.assertTrue(result["checked_at"])
        self.assertEqual(mocked_urlopen.call_args.kwargs["timeout"], 2)
        self.assertTrue(mocked_urlopen.call_args.args[0].full_url.endswith("/health"))

    @patch("dashboard.services.urlopen", side_effect=URLError("service unavailable"))
    def test_health_check_degrades_to_offline(self, mocked_urlopen):
        result = inference_service_health()

        self.assertEqual(result["status"], "offline")
        self.assertIsNone(result["model_version"])
        self.assertTrue(result["checked_at"])
