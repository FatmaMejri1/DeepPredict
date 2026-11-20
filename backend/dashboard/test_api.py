from datetime import datetime, timedelta, timezone
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

    def test_latest_risk_and_anomaly_predictions_are_selected(self):
        older = self.metric.timestamp + timedelta(days=1)
        latest = self.metric.timestamp + timedelta(days=2)
        Prediction.objects.create(
            resource=self.disk,
            model_version=self.ano_model,
            score=1.8,
            is_anomalous=True,
            window_start=older,
            window_end=older,
        )
        Prediction.objects.create(
            resource=self.disk,
            model_version=self.risk_model,
            score=0.92,
            risk_level=RiskLevel.CRITICAL,
            horizon_days=7,
            window_start=latest,
            window_end=latest,
        )
        Prediction.objects.create(
            resource=self.disk,
            model_version=self.ano_model,
            score=0.02,
            is_anomalous=False,
            window_start=latest,
            window_end=latest,
        )
        self.client.force_authenticate(user=self.operator)

        response = self.client.get("/api/drives/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        drive = next(item for item in response.data["results"] if item["id"] == str(self.disk.id))
        self.assertEqual(drive["risk_level"], RiskLevel.CRITICAL)
        self.assertEqual(drive["risk_score"], 0.92)
        self.assertFalse(drive["is_anomalous"])

    def test_drive_filters_and_ordering(self):
        high_drive = Resource.objects.create(
            name="High risk disk",
            identifier="AAA111",
            resource_type=ResourceType.DISK,
            attributes={"model": "MODEL-A"},
            status=Status.HIGH_RISK,
        )
        unscored_drive = Resource.objects.create(
            name="Unscored disk",
            identifier="BBB222",
            resource_type=ResourceType.DISK,
            attributes={"model": "MODEL-B"},
            status=Status.HEALTHY,
        )
        Prediction.objects.create(
            resource=high_drive,
            model_version=self.risk_model,
            score=0.91,
            risk_level=RiskLevel.HIGH,
            horizon_days=7,
            window_start=self.metric.timestamp,
            window_end=self.metric.timestamp,
        )
        self.client.force_authenticate(user=self.operator)

        default_order = self.client.get("/api/drives/")
        high_status = self.client.get("/api/drives/?status=HIGH_RISK")
        search = self.client.get("/api/drives/?search=bbb")
        unscored_filter = self.client.get("/api/drives/?risk_level=NOT_SCORED")
        ascending_risk = self.client.get("/api/drives/?ordering=risk_score")
        identifier_order = self.client.get("/api/drives/?ordering=identifier")
        invalid_filters = self.client.get("/api/drives/?status=nonsense&ordering=x&page=abc")

        self.assertEqual(
            [item["identifier"] for item in default_order.data["results"]],
            ["AAA111", "ZJV001", "BBB222"],
        )
        self.assertEqual([item["identifier"] for item in high_status.data["results"]], ["AAA111"])
        self.assertEqual([item["identifier"] for item in search.data["results"]], ["BBB222"])
        self.assertEqual([item["identifier"] for item in unscored_filter.data["results"]], ["BBB222"])
        self.assertEqual(
            [item["identifier"] for item in ascending_risk.data["results"]],
            ["ZJV001", "AAA111", "BBB222"],
        )
        self.assertEqual(
            [item["identifier"] for item in identifier_order.data["results"]],
            ["AAA111", "BBB222", "ZJV001"],
        )
        self.assertEqual(invalid_filters.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [item["identifier"] for item in invalid_filters.data["results"]],
            ["AAA111", "ZJV001", "BBB222"],
        )

    def test_drive_detail_and_telemetry(self):
        self.client.force_authenticate(user=self.operator)
        detail_resp = self.client.get(f"/api/drives/{self.disk.id}/")
        self.assertEqual(detail_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_resp.data["identifier"], "ZJV001")

        telem_resp = self.client.get(f"/api/drives/{self.disk.id}/telemetry/")
        self.assertEqual(telem_resp.status_code, status.HTTP_200_OK)
        self.assertIn("smart", telem_resp.data)
        self.assertIn("risk", telem_resp.data)

    def test_telemetry_api_prepares_ordered_smart_and_risk_series(self):
        later = self.metric.timestamp + timedelta(days=1)
        Metric.objects.create(
            resource=self.disk,
            timestamp=later,
            values={"smart_5_raw": 7.0, "smart_187_raw": 2.0, "smart_197_raw": 3.0},
        )
        Prediction.objects.create(
            resource=self.disk,
            model_version=self.risk_model,
            score=0.42,
            risk_level=RiskLevel.MEDIUM,
            horizon_days=7,
            window_start=later,
            window_end=later,
        )
        self.client.force_authenticate(user=self.operator)

        response = self.client.get(f"/api/drives/{self.disk.id}/telemetry/?days=2")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        labels = [self.metric.timestamp.strftime("%Y-%m-%d"), later.strftime("%Y-%m-%d")]
        self.assertEqual(response.data["smart"]["labels"], labels)
        self.assertEqual(
            [(series["label"], series["values"]) for series in response.data["smart"]["series"]],
            [
                ("Reallocated sectors (5)", [0.0, 7.0]),
                ("Uncorrectable errors (187)", [0.0, 2.0]),
                ("Pending sectors (197)", [0.0, 3.0]),
            ],
        )
        self.assertEqual(response.data["risk"]["labels"], labels)
        self.assertEqual(response.data["risk"]["scores"], [0.15, 0.42])
        self.assertEqual(response.data["thresholds"], {"medium": 0.35, "high": 0.60, "critical": 0.80})

    def test_unscored_drives_and_unknown_ids_have_stable_responses(self):
        unscored = Resource.objects.create(
            name="Unscored disk",
            identifier="UNSCORED-1",
            resource_type=ResourceType.DISK,
            status=Status.HEALTHY,
        )
        self.client.force_authenticate(user=self.operator)

        list_response = self.client.get("/api/drives/?risk_level=NOT_SCORED")
        detail_response = self.client.get(f"/api/drives/{unscored.id}/")
        unknown_response = self.client.get("/api/drives/00000000-0000-0000-0000-000000000000/")
        invalid_id_response = self.client.get("/api/drives/not-a-uuid/")

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual([item["identifier"] for item in list_response.data["results"]], ["UNSCORED-1"])
        self.assertIsNone(list_response.data["results"][0]["risk_level"])
        self.assertIsNone(list_response.data["results"][0]["risk_score"])
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        self.assertIsNone(detail_response.data["risk_level"])
        self.assertIsNone(detail_response.data["risk_score"])
        self.assertIsNone(detail_response.data["scored_until"])
        self.assertEqual(unknown_response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(invalid_id_response.status_code, status.HTTP_404_NOT_FOUND)

    def test_ml_models_list(self):
        self.client.force_authenticate(user=self.operator)
        resp = self.client.get("/api/ml-models/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 2)

    def test_ml_models_api_exposes_evaluation_protocol_rows_and_thresholds(self):
        self.risk_model.evaluation_metrics = {
            "protocol": "time-based holdout",
            "results": {
                "medium": {"healthy_drives_flagged": 0.03, "failed_drives_detected": 0.75},
                "high": {"healthy_drives_flagged": 0.01, "failed_drives_detected": 0.55},
            },
        }
        self.risk_model.save(update_fields=["evaluation_metrics"])
        self.ano_model.evaluation_metrics = {
            "protocol": "normal-only holdout",
            "results": {"healthy_drives_flagged": 0.02, "failed_drives_detected": 0.14},
        }
        self.ano_model.save(update_fields=["evaluation_metrics"])
        self.client.force_authenticate(user=self.operator)

        response = self.client.get("/api/ml-models/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        risk_card = next(item for item in response.data if item["model_type"] == ModelType.FAILURE_PREDICTION)
        anomaly_card = next(item for item in response.data if item["model_type"] == ModelType.ANOMALY_DETECTION)
        self.assertEqual(risk_card["protocol"], "time-based holdout")
        self.assertEqual(risk_card["evaluation_metrics"], self.risk_model.evaluation_metrics)
        self.assertEqual([row["label"] for row in risk_card["rows"]], ["MEDIUM", "HIGH"])
        self.assertEqual([row["threshold"] for row in risk_card["rows"]], [0.35, 0.60])
        self.assertAlmostEqual(risk_card["rows"][0]["healthy"], 3.0)
        self.assertAlmostEqual(risk_card["rows"][0]["failed"], 75.0)
        self.assertAlmostEqual(risk_card["rows"][1]["healthy"], 1.0)
        self.assertAlmostEqual(risk_card["rows"][1]["failed"], 55.0)
        self.assertEqual(anomaly_card["protocol"], "normal-only holdout")
        self.assertEqual(len(anomaly_card["rows"]), 1)
        self.assertEqual(anomaly_card["rows"][0]["label"], "ANOMALOUS")
        self.assertEqual(anomaly_card["rows"][0]["threshold"], 0.05)
        self.assertAlmostEqual(anomaly_card["rows"][0]["healthy"], 2.0)
        self.assertAlmostEqual(anomaly_card["rows"][0]["failed"], 14.0)

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
