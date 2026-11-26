from datetime import datetime, timedelta, timezone
import uuid
from unittest.mock import MagicMock, patch
from urllib.error import URLError

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import Role
from alerts.models import Alert, AlertSeverity, AlertStatus, AlertType
from audit.models import ActionType, AuditLog
from infrastructure.models import Resource, ResourceType, Status
from ml_models.models import MLModelVersion, ModelType
from monitoring.models import Metric
from predictions.inference_client import DriveModelCompatibilityError
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

    def create_filtered_drive(self, identifier, status_value, risk_level=None, anomaly=None):
        drive = Resource.objects.create(
            name=f"Drive {identifier}",
            identifier=identifier,
            resource_type=ResourceType.DISK,
            status=status_value,
        )
        if risk_level is not None:
            Prediction.objects.create(
                resource=drive,
                model_version=self.risk_model,
                score=0.75,
                risk_level=risk_level,
                horizon_days=7,
                window_start=self.metric.timestamp,
                window_end=self.metric.timestamp,
            )
        if anomaly is not None:
            Prediction.objects.create(
                resource=drive,
                model_version=self.ano_model,
                score=0.9 if anomaly else 0.01,
                is_anomalous=anomaly,
                window_start=self.metric.timestamp,
                window_end=self.metric.timestamp,
            )
        return drive

    def create_prediction_target(self, identifier, with_history=True):
        drive = Resource.objects.create(
            name=f"Prediction target {identifier}",
            identifier=identifier,
            resource_type=ResourceType.DISK,
        )
        if with_history:
            now = datetime.now(timezone.utc)
            for days_back in range(20):
                Metric.objects.create(
                    resource=drive,
                    timestamp=now - timedelta(days=19 - days_back),
                    values={"smart_5_raw": days_back},
                )
        return drive

    def fake_prediction_answer(self):
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=13)
        return {
            "risk_score": 0.7,
            "risk_level": "HIGH",
            "horizon_days": 7,
            "anomaly_score": 0.2,
            "is_anomalous": False,
            "window_start": start.isoformat(),
            "window_end": end.isoformat(),
            "model_version": self.risk_model.version,
        }

    def test_summary_api_authenticated(self):
        self.client.force_authenticate(user=self.operator)
        resp = self.client.get("/api/dashboard/summary/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("total", resp.data)
        self.assertIn("healthy", resp.data)
        self.assertIn("top_critical", resp.data)

    def test_training_and_demo_records_are_excluded_from_operational_endpoints(self):
        now = datetime.now(timezone.utc)
        demo_drive = Resource.objects.create(
            name="Training sample", identifier="TRAINING-DEMO-001",
            resource_type=ResourceType.DISK, attributes={"demo": True},
            status=Status.HIGH_RISK,
        )
        replay_drive = Resource.objects.create(
            name="Backblaze sample", identifier="TRAINING-REPLAY-001",
            resource_type=ResourceType.DISK, status=Status.HIGH_RISK,
        )
        for drive, source in ((demo_drive, "API_UPLOAD"), (replay_drive, "BACKBLAZE_REPLAY")):
            Metric.objects.create(
                resource=drive, timestamp=now, source=source,
                values={"smart_5_raw": 99},
            )
            risk = Prediction.objects.create(
                resource=drive, model_version=self.risk_model, score=0.99,
                risk_level=RiskLevel.CRITICAL, horizon_days=7,
                window_start=now - timedelta(days=13), window_end=now,
            )
            Alert.objects.create(
                resource=drive, latest_prediction=risk,
                alert_type=AlertType.FAILURE_RISK, severity=AlertSeverity.CRITICAL,
                status=AlertStatus.OPEN, first_seen_at=now, last_seen_at=now,
            )

        self.client.force_authenticate(user=self.operator)
        drives = self.client.get("/api/drives/")
        summary = self.client.get("/api/dashboard/summary/")
        activity = self.client.get("/api/dashboard/activity/")
        alerts = self.client.get("/api/alerts/")
        unread = self.client.get("/api/alerts/unread-count/")

        self.assertEqual(drives.data["count"], 1)
        self.assertEqual([row["identifier"] for row in drives.data["results"]], [self.disk.identifier])
        self.assertEqual(summary.data["total"], 1)
        self.assertEqual(summary.data["data_until"], self.metric.timestamp.isoformat())
        self.assertEqual({row["drive_identifier"] for row in activity.data["results"]}, {self.disk.identifier})
        self.assertEqual(alerts.data["count"], 0)
        self.assertEqual(unread.data["count"], 0)
        self.assertEqual(
            self.client.get(f"/api/drives/{demo_drive.pk}/").status_code,
            status.HTTP_404_NOT_FOUND,
        )
        self.assertEqual(
            self.client.get(f"/api/drives/{replay_drive.pk}/telemetry/").status_code,
            status.HTTP_404_NOT_FOUND,
        )
        self.assertEqual(
            self.client.get(f"/api/drives/{demo_drive.pk}/timeline/").status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_prediction_and_telemetry_upload_reject_training_resources(self):
        demo_drive = Resource.objects.create(
            name="Training sample", identifier="TRAINING-RESERVED-001",
            resource_type=ResourceType.DISK, attributes={"demo": True},
        )
        Metric.objects.create(
            resource=demo_drive, timestamp=datetime.now(timezone.utc),
            source="backblaze", values={"smart_5_raw": 10},
        )
        self.client.force_authenticate(user=self.it_pro)

        with patch("dashboard.api_views.predict_resource") as predict_resource:
            prediction_response = self.client.post(
                "/api/predictions/predict/", {"resource_id": str(demo_drive.pk)}, format="json"
            )
        upload_response = self.client.post(
            "/api/telemetry/upload/",
            {"readings": [{"serial_number": demo_drive.identifier, "date": "2026-11-10", "smart_5_raw": 1}]},
            format="json",
        )

        self.assertEqual(prediction_response.status_code, status.HTTP_404_NOT_FOUND)
        predict_resource.assert_not_called()
        self.assertEqual(upload_response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(Metric.objects.filter(resource=demo_drive).count(), 1)

    def test_dashboard_status_filter_applies_to_kpis_top_drives_and_activity(self):
        warning_drive = self.create_filtered_drive("WARN-001", Status.WARNING, "MEDIUM", True)
        self.client.force_authenticate(user=self.operator)

        summary = self.client.get("/api/dashboard/summary/?status=warning")
        activity = self.client.get("/api/dashboard/activity/?status=WARNING")

        self.assertEqual(summary.status_code, status.HTTP_200_OK)
        self.assertEqual(summary.data["total"], 1)
        self.assertEqual(summary.data["healthy"], 0)
        self.assertEqual(summary.data["warning"], 1)
        self.assertEqual(summary.data["high_risk"], 0)
        self.assertEqual([row["identifier"] for row in summary.data["top_critical"]], ["WARN-001"])
        self.assertEqual({row["drive_identifier"] for row in activity.data["results"]}, {warning_drive.identifier})

    def test_dashboard_risk_and_anomaly_filters_match_drive_filter_semantics(self):
        self.create_filtered_drive("RISK-001", Status.HIGH_RISK, "CRITICAL", True)
        not_scored = self.create_filtered_drive("UNSCORED-001", Status.HEALTHY)
        normal = self.create_filtered_drive("NORMAL-001", Status.HEALTHY, "LOW", False)
        self.client.force_authenticate(user=self.operator)

        risk = self.client.get("/api/dashboard/summary/?risk_level=critical")
        not_scored_response = self.client.get("/api/dashboard/summary/?risk_level=not_scored")
        anomalous = self.client.get("/api/dashboard/summary/?is_anomalous=1")
        normal_or_unevaluated = self.client.get("/api/dashboard/summary/?is_anomalous=false")

        self.assertEqual(risk.data["total"], 1)
        self.assertEqual(risk.data["high_risk"], 1)
        self.assertEqual(not_scored_response.data["total"], 1)
        self.assertEqual(not_scored_response.data["not_scored"], 1)
        self.assertEqual(not_scored_response.data["top_critical"], [])
        self.assertEqual(anomalous.data["total"], 1)
        self.assertEqual(anomalous.data["anomalous"], 1)
        self.assertEqual(
            {row["identifier"] for row in normal_or_unevaluated.data["top_critical"]},
            {self.disk.identifier, normal.identifier},
        )
        self.assertEqual(
            self.client.get("/api/dashboard/activity/?risk_level=NOT_SCORED").data["results"],
            [],
        )
        self.assertEqual(not_scored.status, Status.HEALTHY)

    def test_dashboard_combined_filters_are_applied_consistently(self):
        selected = self.create_filtered_drive("MATCH-001", Status.WARNING, "MEDIUM", True)
        self.create_filtered_drive("NO-ANOMALY-001", Status.WARNING, "MEDIUM", False)
        self.create_filtered_drive("OTHER-STATUS-001", Status.HIGH_RISK, "MEDIUM", True)
        self.client.force_authenticate(user=self.operator)

        query = "status=WARNING&risk_level=MEDIUM&is_anomalous=true"
        summary = self.client.get(f"/api/dashboard/summary/?{query}")
        activity = self.client.get(f"/api/dashboard/activity/?{query}")

        self.assertEqual(summary.data["total"], 1)
        self.assertEqual([row["identifier"] for row in summary.data["top_critical"]], [selected.identifier])
        self.assertEqual({row["drive_identifier"] for row in activity.data["results"]}, {selected.identifier})

    def test_dashboard_invalid_filters_and_unfiltered_contract_are_unchanged(self):
        self.client.force_authenticate(user=self.operator)

        summary = self.client.get("/api/dashboard/summary/")
        summary_with_invalid_filters = self.client.get(
            "/api/dashboard/summary/?status=bad&risk_level=unknown&is_anomalous=maybe"
        )
        activity = self.client.get("/api/dashboard/activity/")
        activity_with_invalid_filters = self.client.get(
            "/api/dashboard/activity/?status=bad&risk_level=unknown&is_anomalous=maybe"
        )

        self.assertEqual(summary.status_code, status.HTTP_200_OK)
        self.assertEqual(summary.data, summary_with_invalid_filters.data)
        self.assertEqual(set(summary.data), {
            "total", "healthy", "warning", "high_risk", "anomalous", "not_scored", "data_until", "top_critical"
        })
        self.assertEqual(activity.status_code, status.HTTP_200_OK)
        self.assertEqual(activity.data, activity_with_invalid_filters.data)
        self.assertEqual(set(activity.data), {"results"})

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
        self.assertTrue(drive["anomaly_evaluated"])

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
        unscored = next(item for item in invalid_filters.data["results"] if item["id"] == str(unscored_drive.id))
        self.assertFalse(unscored["anomaly_evaluated"])

    def test_drive_detail_and_telemetry(self):
        self.client.force_authenticate(user=self.operator)
        detail_resp = self.client.get(f"/api/drives/{self.disk.id}/")
        self.assertEqual(detail_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_resp.data["identifier"], "ZJV001")
        self.assertFalse(detail_resp.data["anomaly_evaluated"])

        telem_resp = self.client.get(f"/api/drives/{self.disk.id}/telemetry/")
        self.assertEqual(telem_resp.status_code, status.HTTP_200_OK)
        self.assertIn("smart", telem_resp.data)
        self.assertIn("risk", telem_resp.data)

    def test_drive_prediction_history_returns_latest_twenty_with_model_context(self):
        self.client.force_authenticate(user=self.operator)
        anomaly = Prediction.objects.create(
            resource=self.disk,
            model_version=self.ano_model,
            score=1.4,
            is_anomalous=True,
            window_start=self.metric.timestamp - timedelta(days=13),
            window_end=self.metric.timestamp,
        )

        response = self.client.get(f"/api/drives/{self.disk.id}/predictions/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual([item["score"] for item in response.data], [1.4, 0.15])
        anomaly_result = response.data[0]
        self.assertEqual(anomaly_result["prediction_type"], ModelType.ANOMALY_DETECTION)
        self.assertEqual(anomaly_result["score"], 1.4)
        self.assertTrue(anomaly_result["is_anomalous"])
        self.assertEqual(anomaly_result["window_start"], anomaly.window_start.isoformat())
        self.assertEqual(anomaly_result["window_end"], anomaly.window_end.isoformat())
        self.assertEqual(anomaly_result["created_at"], anomaly.created_at.isoformat())
        self.assertEqual(anomaly_result["model"], {
            "name": self.ano_model.name,
            "version": self.ano_model.version,
            "model_type": self.ano_model.model_type,
            "architecture": self.ano_model.architecture,
        })

    def test_drive_prediction_history_requires_authentication_and_valid_drive(self):
        unauthenticated = self.client.get(f"/api/drives/{self.disk.id}/predictions/")
        self.assertEqual(unauthenticated.status_code, status.HTTP_401_UNAUTHORIZED)

        self.client.force_authenticate(user=self.operator)
        unknown = self.client.get("/api/drives/00000000-0000-0000-0000-000000000000/predictions/")
        self.assertEqual(unknown.status_code, status.HTTP_404_NOT_FOUND)

    def test_drive_timeline_requires_authentication_and_all_roles_can_read(self):
        url = f"/api/drives/{self.disk.id}/timeline/"
        self.assertEqual(self.client.get(url).status_code, status.HTTP_401_UNAUTHORIZED)

        for user in (self.sysadmin, self.it_pro, self.operator):
            with self.subTest(role=user.role):
                self.client.force_authenticate(user=user)
                response = self.client.get(url)
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertEqual(set(response.data), {"count", "next", "previous", "results"})

    def test_drive_timeline_is_resource_scoped_and_hides_missing_or_inactive_drives(self):
        other = Resource.objects.create(
            name="Other timeline drive", identifier="OTHER-TIMELINE", resource_type=ResourceType.DISK,
        )
        Metric.objects.create(
            resource=other, timestamp=self.metric.timestamp + timedelta(days=1),
            values={"smart_5_raw": 999}, source="OTHER_SOURCE",
        )
        self.client.force_authenticate(user=self.operator)

        response = self.client.get(f"/api/drives/{self.disk.id}/timeline/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(all(item["resource"]["id"] == str(self.disk.id) for item in response.data["results"]))
        self.assertNotIn("OTHER-TIMELINE", str(response.data))

        missing = self.client.get("/api/drives/00000000-0000-0000-0000-000000000000/timeline/")
        self.assertEqual(missing.status_code, status.HTTP_404_NOT_FOUND)
        self.disk.is_active = False
        self.disk.save(update_fields=("is_active",))
        inactive = self.client.get(f"/api/drives/{self.disk.id}/timeline/")
        self.assertEqual(inactive.status_code, status.HTTP_404_NOT_FOUND)

    def test_drive_timeline_emits_all_alert_milestones_without_fabricating_recurrences(self):
        from django.utils import timezone

        opened_at = self.metric.timestamp - timedelta(hours=4)
        acknowledged_at = opened_at + timedelta(hours=1)
        auto_resolved_at = opened_at + timedelta(hours=2)
        user_resolved_at = opened_at + timedelta(hours=3)
        opened = Alert.objects.create(
            resource=self.disk, alert_type=AlertType.FAILURE_RISK, severity=AlertSeverity.HIGH,
            first_seen_at=opened_at, last_seen_at=opened_at + timedelta(minutes=1), occurrence_count=7,
        )
        acknowledged = Alert.objects.create(
            resource=self.disk, alert_type=AlertType.ANOMALY, severity=AlertSeverity.HIGH,
            status=AlertStatus.ACKNOWLEDGED, first_seen_at=opened_at, last_seen_at=acknowledged_at,
            acknowledged_at=acknowledged_at, acknowledged_by=self.operator,
        )
        automatic = Alert.objects.create(
            resource=self.disk, alert_type=AlertType.FAILURE_RISK, severity=AlertSeverity.CRITICAL,
            status=AlertStatus.RESOLVED, first_seen_at=opened_at, last_seen_at=auto_resolved_at,
            resolved_at=auto_resolved_at, resolution_source="AUTO", consecutive_clear_count=2,
        )
        manual = Alert.objects.create(
            resource=self.disk, alert_type=AlertType.ANOMALY, severity=AlertSeverity.HIGH,
            status=AlertStatus.RESOLVED, first_seen_at=opened_at, last_seen_at=user_resolved_at,
            resolved_at=user_resolved_at, resolved_by=self.it_pro, resolution_source="USER",
        )
        self.client.force_authenticate(user=self.operator)

        response = self.client.get(f"/api/drives/{self.disk.id}/timeline/?type=ALERT_OPENED")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 4)
        opened_event = next(event for event in response.data["results"] if event["id"].endswith(str(opened.pk)))
        self.assertEqual(opened_event["occurred_at"], opened_at.isoformat())
        self.assertNotIn("occurrence_count", opened_event["data"])
        self.assertEqual(opened_event["data"]["alert_type"], AlertType.FAILURE_RISK)

        ack_response = self.client.get(f"/api/drives/{self.disk.id}/timeline/?type=ALERT_ACKNOWLEDGED")
        self.assertEqual(ack_response.data["count"], 1)
        self.assertEqual(ack_response.data["results"][0]["actor"], self.operator.username)
        self.assertEqual(ack_response.data["results"][0]["occurred_at"], acknowledged_at.isoformat())

        resolved_response = self.client.get(f"/api/drives/{self.disk.id}/timeline/?type=ALERT_RESOLVED")
        self.assertEqual(resolved_response.data["count"], 2)
        resolved_by_id = {event["data"]["alert_id"]: event for event in resolved_response.data["results"]}
        self.assertEqual(resolved_by_id[str(automatic.pk)]["data"]["resolution_source"], "AUTO")
        self.assertIsNone(resolved_by_id[str(automatic.pk)]["actor"])
        self.assertEqual(resolved_by_id[str(manual.pk)]["data"]["resolution_source"], "USER")
        self.assertEqual(resolved_by_id[str(manual.pk)]["actor"], self.it_pro.username)
        self.assertNotIn("ALERT_OCCURRENCE", str(response.data))

    def test_drive_timeline_projects_safe_audit_and_telemetry_fields(self):
        AuditLog.objects.create(
            user=self.it_pro,
            action=ActionType.UPDATE,
            resource_type="Resource",
            resource_id=str(self.disk.pk),
            ip_address="192.0.2.10",
            details={"password": "must-not-leak", "before": {"status": "HEALTHY"}},
        )
        AuditLog.objects.create(
            user=self.it_pro,
            action=ActionType.PREDICT_RUN,
            resource_type="Resource",
            resource_id=str(self.disk.pk),
            details={"risk_score": 0.42},
        )
        self.client.force_authenticate(user=self.operator)

        response = self.client.get(f"/api/drives/{self.disk.id}/timeline/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        metric_event = next(event for event in response.data["results"] if event["event_type"] == "TELEMETRY_READING")
        prediction_event = next(event for event in response.data["results"] if event["event_type"] == "PREDICTION")
        audit_events = [event for event in response.data["results"] if event["event_type"] == "RESOURCE_AUDIT"]
        self.assertEqual(metric_event["occurred_at"], self.metric.timestamp.isoformat())
        self.assertEqual(metric_event["data"], {"source": ""})
        self.assertNotIn("values", metric_event["data"])
        self.assertEqual(prediction_event["actor"], None)
        prediction = Prediction.objects.get(resource=self.disk)
        self.assertEqual(prediction_event["occurred_at"], prediction.created_at.isoformat())
        self.assertEqual(prediction_event["data"]["model"], {
            "name": self.risk_model.name,
            "version": self.risk_model.version,
            "model_type": self.risk_model.model_type,
            "architecture": self.risk_model.architecture,
        })
        self.assertEqual(prediction_event["data"]["prediction_type"], ModelType.FAILURE_PREDICTION)
        self.assertEqual(len(audit_events), 1)
        self.assertEqual(audit_events[0]["data"], {
            "action": ActionType.UPDATE,
            "description": "Resource updated",
        })
        self.assertEqual(audit_events[0]["actor"], self.it_pro.username)
        update_audit = AuditLog.objects.get(action=ActionType.UPDATE)
        self.assertEqual(audit_events[0]["occurred_at"], update_audit.timestamp.isoformat())
        self.assertNotIn("192.0.2.10", str(response.data))
        self.assertNotIn("must-not-leak", str(response.data))
        self.assertNotIn("ip_address", str(response.data))
        self.assertNotIn("PREDICT_RUN", str(response.data))

    def test_drive_timeline_orders_equal_timestamps_deterministically(self):
        prediction = Prediction.objects.filter(resource=self.disk).first()
        Prediction.objects.filter(pk=prediction.pk).update(created_at=self.metric.timestamp)
        AuditLog.objects.create(
            action=ActionType.UPDATE, resource_type="Resource", resource_id=str(self.disk.pk),
        )
        audit = AuditLog.objects.filter(resource_type="Resource", resource_id=str(self.disk.pk)).latest("timestamp")
        AuditLog.objects.filter(pk=audit.pk).update(timestamp=self.metric.timestamp)
        self.client.force_authenticate(user=self.operator)

        response = self.client.get(
            f"/api/drives/{self.disk.id}/timeline/",
            {"from": self.metric.timestamp.isoformat(), "to": self.metric.timestamp.isoformat()},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        event_types = [event["event_type"] for event in response.data["results"]]
        self.assertEqual(event_types, ["PREDICTION", "RESOURCE_AUDIT", "TELEMETRY_READING"])

        paged_first = self.client.get(
            f"/api/drives/{self.disk.id}/timeline/",
            {"from": self.metric.timestamp.isoformat(), "to": self.metric.timestamp.isoformat(), "page_size": 2},
        )
        paged_second = self.client.get(
            f"/api/drives/{self.disk.id}/timeline/",
            {
                "from": self.metric.timestamp.isoformat(), "to": self.metric.timestamp.isoformat(),
                "page_size": 2, "page": 2,
            },
        )
        self.assertEqual(paged_first.data["count"], 3)
        self.assertEqual([event["event_type"] for event in paged_first.data["results"]], event_types[:2])
        self.assertIsNotNone(paged_first.data["next"])
        self.assertEqual([event["event_type"] for event in paged_second.data["results"]], event_types[2:])
        self.assertIsNotNone(paged_second.data["previous"])
        self.assertIsNone(paged_second.data["next"])

    def test_drive_timeline_filters_validation_pagination_and_count(self):
        for index in range(5):
            Metric.objects.create(
                resource=self.disk,
                timestamp=self.metric.timestamp + timedelta(minutes=index + 1),
                values={"smart_5_raw": index}, source="API_UPLOAD",
            )
        self.client.force_authenticate(user=self.operator)
        url = f"/api/drives/{self.disk.id}/timeline/"
        first = self.client.get(url, {"type": "TELEMETRY_READING", "page": 1, "page_size": 2})
        second = self.client.get(url, {"type": "TELEMETRY_READING", "page": 2, "page_size": 2})
        third = self.client.get(url, {"type": "TELEMETRY_READING", "page": 3, "page_size": 2})
        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertEqual(first.data["count"], 6)
        self.assertEqual(len(first.data["results"]), 2)
        self.assertIsNone(first.data["previous"])
        self.assertIsNotNone(first.data["next"])
        self.assertEqual(len(second.data["results"]), 2)
        self.assertIsNotNone(second.data["previous"])
        self.assertIsNotNone(second.data["next"])
        self.assertEqual(len(third.data["results"]), 2)
        self.assertIsNone(third.data["next"])
        self.assertEqual(self.client.get(url, {"type": "PREDICTION"}).data["count"], 1)
        filtered = self.client.get(url, {
            "type": "TELEMETRY_READING",
            "from": (self.metric.timestamp + timedelta(minutes=2)).isoformat(),
            "to": (self.metric.timestamp + timedelta(minutes=3)).isoformat(),
        })
        self.assertEqual(filtered.data["count"], 2)
        self.assertEqual(self.client.get(url, {"type": "BOGUS"}).status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.client.get(url, {"from": "not-a-date"}).status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.client.get(url, {
            "from": "2026-02-01", "to": "2026-01-01",
        }).status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.client.get(url, {"page": "abc"}).status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.client.get(url, {"page": 0}).status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.client.get(url, {"page_size": 101}).status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.client.get(url, {"page_size": 0}).status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.client.get(url, {"type": "TELEMETRY_READING", "page": 4, "page_size": 2}).status_code, status.HTTP_404_NOT_FOUND)

    def test_drive_timeline_uses_a_constant_number_of_queries_without_n_plus_one(self):
        from django.utils import timezone

        stamp = self.metric.timestamp
        Alert.objects.create(
            resource=self.disk, alert_type=AlertType.FAILURE_RISK, severity=AlertSeverity.HIGH,
            first_seen_at=stamp, last_seen_at=stamp,
        )
        Alert.objects.create(
            resource=self.disk, alert_type=AlertType.ANOMALY, severity=AlertSeverity.HIGH,
            status=AlertStatus.ACKNOWLEDGED, first_seen_at=stamp, last_seen_at=stamp,
            acknowledged_at=stamp, acknowledged_by=self.it_pro,
        )
        Alert.objects.create(
            resource=self.disk, alert_type=AlertType.FAILURE_RISK, severity=AlertSeverity.CRITICAL,
            status=AlertStatus.RESOLVED, first_seen_at=stamp, last_seen_at=stamp,
            resolved_at=stamp, resolution_source="AUTO", consecutive_clear_count=2,
        )
        AuditLog.objects.create(
            action=ActionType.UPDATE, resource_type="Resource", resource_id=str(self.disk.pk),
        )
        self.client.force_authenticate(user=self.operator)
        with self.assertNumQueries(13):
            response = self.client.get(f"/api/drives/{self.disk.id}/timeline/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

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

    def test_telemetry_upload_persists_model_under_legacy_and_authoritative_keys(self):
        self.client.force_authenticate(user=self.it_pro)
        response = self.client.post(
            "/api/telemetry/upload/",
            {
                "readings": [{
                    "serial_number": "MODEL-METADATA-001",
                    "model": "ST12000NM0008",
                    "date": "2026-11-10",
                    "smart_5_raw": 12,
                }]
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        drive = Resource.objects.get(identifier="MODEL-METADATA-001")
        self.assertEqual(drive.attributes["drive_model"], "ST12000NM0008")
        self.assertEqual(drive.attributes["model"], "ST12000NM0008")

    @patch("predictions.services.inference_client.predict")
    def test_upload_without_model_keeps_metadata_missing_and_prediction_is_rejected(self, predict):
        self.client.force_authenticate(user=self.it_pro)
        today = datetime.now(timezone.utc).date()
        readings = [
            {
                "serial_number": "MODEL-METADATA-MISSING-001",
                "date": (today - timedelta(days=19 - offset)).isoformat(),
                "smart_5_raw": offset,
            }
            for offset in range(20)
        ]

        upload_response = self.client.post(
            "/api/telemetry/upload/", {"readings": readings}, format="json"
        )

        self.assertEqual(upload_response.status_code, status.HTTP_200_OK)
        drive = Resource.objects.get(identifier="MODEL-METADATA-MISSING-001")
        self.assertNotIn("model", drive.attributes)
        self.assertNotIn("drive_model", drive.attributes)

        prediction_response = self.client.post(
            "/api/predictions/predict/", {"resource_id": str(drive.pk)}, format="json"
        )

        self.assertEqual(prediction_response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        self.assertEqual(prediction_response.data["errors"][0]["code"], "model_compatibility_error")
        self.assertEqual(Prediction.objects.filter(resource=drive).count(), 0)
        predict.assert_not_called()

    @patch(
        "predictions.services.inference_client.predict",
        side_effect=DriveModelCompatibilityError("compatibility could not be verified"),
    )
    def test_unsupported_uploaded_model_returns_validation_failure_without_persisting(self, predict):
        self.client.force_authenticate(user=self.it_pro)
        today = datetime.now(timezone.utc).date()
        readings = [
            {
                "serial_number": "MODEL-METADATA-UNSUPPORTED-001",
                "model": "UNSUPPORTED-DRIVE-MODEL",
                "date": (today - timedelta(days=19 - offset)).isoformat(),
                "smart_5_raw": offset,
            }
            for offset in range(20)
        ]
        upload_response = self.client.post(
            "/api/telemetry/upload/", {"readings": readings}, format="json"
        )
        self.assertEqual(upload_response.status_code, status.HTTP_200_OK)
        drive = Resource.objects.get(identifier="MODEL-METADATA-UNSUPPORTED-001")
        self.assertEqual(drive.attributes["drive_model"], "UNSUPPORTED-DRIVE-MODEL")

        prediction_response = self.client.post(
            "/api/predictions/predict/", {"resource_id": str(drive.pk)}, format="json"
        )

        self.assertEqual(prediction_response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        self.assertEqual(prediction_response.data["errors"][0]["code"], "model_compatibility_error")
        self.assertEqual(Prediction.objects.filter(resource=drive).count(), 0)
        predict.assert_called_once()

    @patch("predictions.services.inference_client.predict")
    def test_it_pro_upload_then_prediction_persists_and_attributes_independent_results(self, predict):
        self.client.force_authenticate(user=self.it_pro)
        today = datetime.now(timezone.utc).date()
        readings = [
            {
                "serial_number": "ITPRO-WORKFLOW-001",
                "model": "ST12000NM0008",
                "date": (today - timedelta(days=19 - offset)).isoformat(),
                "smart_5_raw": offset * 2,
                "smart_187_raw": 0,
                "smart_197_raw": offset,
            }
            for offset in range(20)
        ]

        upload_response = self.client.post(
            "/api/telemetry/upload/", {"readings": readings}, format="json"
        )

        self.assertEqual(upload_response.status_code, status.HTTP_200_OK)
        self.assertEqual(upload_response.data["status"], "success")
        self.assertEqual(upload_response.data["ingested_readings"], 20)
        drive = Resource.objects.get(identifier="ITPRO-WORKFLOW-001")
        self.assertEqual(Metric.objects.filter(resource=drive).count(), 20)
        self.assertEqual(drive.attributes["drive_model"], "ST12000NM0008")

        predict.return_value = self.fake_prediction_answer()
        prediction_response = self.client.post(
            "/api/predictions/predict/", {"resource_id": str(drive.pk)}, format="json"
        )

        self.assertEqual(prediction_response.status_code, status.HTTP_200_OK)
        self.assertEqual(prediction_response.data["outcome"], "full_success")
        self.assertEqual(prediction_response.data["scored_count"], 1)
        self.assertEqual(Prediction.objects.filter(resource=drive).count(), 2)
        sent_readings = predict.call_args.args[0]
        self.assertEqual(len(sent_readings), 20)
        self.assertEqual({row["model"] for row in sent_readings}, {"ST12000NM0008"})
        self.assertEqual([row["smart_5_raw"] for row in sent_readings], [i * 2 for i in range(20)])

        risk_prediction = Prediction.objects.get(resource=drive, model_version=self.risk_model)
        anomaly_prediction = Prediction.objects.get(resource=drive, model_version=self.ano_model)
        self.assertEqual(risk_prediction.risk_level, "HIGH")
        self.assertEqual(risk_prediction.score, 0.7)
        self.assertIsNone(risk_prediction.is_anomalous)
        self.assertIsNone(anomaly_prediction.risk_level)
        self.assertFalse(anomaly_prediction.is_anomalous)
        self.assertEqual(anomaly_prediction.score, 0.2)

        drive.refresh_from_db()
        self.assertEqual(drive.status, Status.HIGH_RISK)
        self.assertTrue(Alert.objects.filter(
            resource=drive, alert_type=AlertType.FAILURE_RISK, status=AlertStatus.OPEN
        ).exists())
        self.assertFalse(Alert.objects.filter(resource=drive, alert_type=AlertType.ANOMALY).exists())
        upload_audit = AuditLog.objects.get(action=ActionType.TELEMETRY_UPLOAD)
        prediction_audit = AuditLog.objects.get(
            action=ActionType.PREDICT_RUN, resource_id=str(drive.pk)
        )
        self.assertEqual(upload_audit.user, self.it_pro)
        self.assertEqual(prediction_audit.user, self.it_pro)
        self.assertEqual(prediction_audit.details["source"], "api")

    def test_telemetry_validation_requires_authentication(self):
        response = self.client.post(
            "/api/telemetry/validate/",
            {"readings": [{"date": "2026-11-01", "smart_5_raw": 10}]},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch("urllib.request.urlopen", side_effect=URLError("AI service unavailable"))
    def test_all_roles_can_access_telemetry_validation(self, _urlopen):
        readings = [{"date": "2026-11-01", "smart_5_raw": 10}]

        for user in (self.sysadmin, self.it_pro, self.operator):
            with self.subTest(role=user.role):
                self.client.force_authenticate(user=user)
                response = self.client.post(
                    "/api/telemetry/validate/",
                    {"readings": readings},
                    format="json",
                )

                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertIn("ready_for_prediction", response.data)
                self.assertEqual(response.data["metrics"]["total_readings"], 1)

    @patch("audit.services.AuditLog.objects.create", side_effect=IntegrityError("audit unavailable"))
    def test_telemetry_upload_rolls_back_when_audit_write_fails(self, _create):
        self.client.force_authenticate(user=self.it_pro)
        with self.assertRaises(IntegrityError):
            self.client.post(
                "/api/telemetry/upload/",
                {"readings": [{"serial_number": "AUDIT-ROLLBACK", "date": "2026-11-02", "smart_5_raw": 4}]},
                format="json",
            )
        self.assertFalse(Resource.objects.filter(identifier="AUDIT-ROLLBACK").exists())

    @patch("predictions.services.inference_client.predict")
    def test_prediction_api_audit_records_authenticated_actor(self, predict):
        drive = Resource.objects.create(
            name="Prediction audit drive", identifier="PRED-AUDIT", resource_type=ResourceType.DISK
        )
        now = datetime.now(timezone.utc)
        for days_back in range(20):
            Metric.objects.create(
                resource=drive,
                timestamp=now - timedelta(days=19 - days_back),
                values={"smart_5_raw": days_back},
            )
        start, end = now - timedelta(days=13), now
        predict.return_value = {
            "risk_score": 0.7, "risk_level": "HIGH", "horizon_days": 7,
            "anomaly_score": 0.2, "is_anomalous": False,
            "window_start": start.isoformat(), "window_end": end.isoformat(),
            "model_version": self.risk_model.version,
        }
        self.client.force_authenticate(user=self.it_pro)

        response = self.client.post("/api/predictions/predict/", {"resource_id": str(drive.pk)}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["outcome"], "full_success")
        self.assertEqual(response.data["scored_count"], 1)
        self.assertEqual(Prediction.objects.filter(resource=drive).count(), 2)
        event = AuditLog.objects.get(action=ActionType.PREDICT_RUN, resource_id=str(drive.pk))
        self.assertEqual(event.user, self.it_pro)
        self.assertEqual(event.details["source"], "api")

    @patch("predictions.services.inference_client.predict")
    def test_sysadmin_is_authorized_to_generate_predictions(self, predict):
        drive = self.create_prediction_target("PRED-SYSADMIN")
        predict.return_value = self.fake_prediction_answer()
        self.client.force_authenticate(user=self.sysadmin)

        response = self.client.post(
            "/api/predictions/predict/",
            {"resource_id": str(drive.pk)},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["outcome"], "full_success")
        self.assertEqual(response.data["scored_count"], 1)
        self.assertEqual(Prediction.objects.filter(resource=drive).count(), 2)
        event = AuditLog.objects.get(action=ActionType.PREDICT_RUN, resource_id=str(drive.pk))
        self.assertEqual(event.user, self.sysadmin)
        self.assertEqual(event.details["source"], "api")

    @patch("predictions.services.inference_client.predict")
    def test_prediction_api_partial_success_only_reports_committed_resources(self, predict):
        self.disk.is_active = False
        self.disk.save(update_fields=["is_active"])
        successful_drive = self.create_prediction_target("PRED-PARTIAL-OK")
        no_history_drive = self.create_prediction_target("PRED-PARTIAL-EMPTY", with_history=False)
        predict.return_value = self.fake_prediction_answer()
        self.client.force_authenticate(user=self.it_pro)

        response = self.client.post("/api/predictions/predict/", {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_207_MULTI_STATUS)
        self.assertEqual(response.data["outcome"], "partial_success")
        self.assertEqual(response.data["scored_count"], 1)
        self.assertEqual([row["identifier"] for row in response.data["results"]], [successful_drive.identifier])
        self.assertEqual([row["identifier"] for row in response.data["errors"]], [no_history_drive.identifier])
        self.assertEqual(Prediction.objects.filter(resource=successful_drive).count(), 2)
        self.assertEqual(Prediction.objects.filter(resource=no_history_drive).count(), 0)

    @patch("predictions.services.log_action", side_effect=IntegrityError("private database detail"))
    @patch("predictions.services.inference_client.predict")
    def test_prediction_api_audit_failure_is_safe_complete_failure_and_rolls_back(self, predict, _log_action):
        self.disk.is_active = False
        self.disk.save(update_fields=["is_active"])
        drive = self.create_prediction_target("PRED-AUDIT-FAIL")
        predict.return_value = self.fake_prediction_answer()
        self.client.force_authenticate(user=self.it_pro)

        response = self.client.post(
            "/api/predictions/predict/", {"resource_id": str(drive.pk)}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(response.data["outcome"], "complete_failure")
        self.assertEqual(response.data["scored_count"], 0)
        self.assertEqual(response.data["results"], [])
        self.assertEqual(response.data["errors"][0]["code"], "internal_error")
        self.assertNotIn("private database detail", str(response.data))
        self.assertEqual(Prediction.objects.filter(resource=drive).count(), 0)
        drive.refresh_from_db()
        self.assertEqual(drive.status, Status.HEALTHY)

    def test_prediction_api_complete_failure_has_distinct_contract(self):
        self.disk.is_active = False
        self.disk.save(update_fields=["is_active"])
        drive = self.create_prediction_target("PRED-COMPLETE-EMPTY", with_history=False)
        self.client.force_authenticate(user=self.it_pro)

        response = self.client.post(
            "/api/predictions/predict/", {"resource_id": str(drive.pk)}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        self.assertEqual(response.data["outcome"], "complete_failure")
        self.assertEqual(response.data["scored_count"], 0)
        self.assertEqual(response.data["results"], [])
        self.assertEqual(response.data["errors"][0]["code"], "no_new_prediction")
        self.assertEqual(Prediction.objects.filter(resource=drive).count(), 0)


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
