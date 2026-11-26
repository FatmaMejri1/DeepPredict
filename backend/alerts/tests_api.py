import uuid
from datetime import timedelta
from unittest.mock import patch

from django.db import IntegrityError
from django.test import override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import Role, User
from alerts.models import Alert, AlertSeverity, AlertStatus, AlertType
from audit.models import ActionType, AuditLog
from infrastructure.models import Resource, ResourceType, Status
from ml_models.models import MLModelVersion, ModelType
from predictions.models import Prediction


@override_settings(RATELIMIT_ENABLE=False)
class AlertsAPITests(APITestCase):
    def setUp(self):
        self.users = {
            role: User.objects.create_user(
                username=f"alert-{role.lower()}",
                email=f"alert-{role.lower()}@example.test",
                password="test-password",
                role=role,
            )
            for role in (Role.SYSADMIN, Role.IT_PRO, Role.OPERATOR)
        }
        self.resource = Resource.objects.create(
            name="Alert drive", identifier="ALERT-API-1", resource_type=ResourceType.DISK,
            status=Status.HIGH_RISK,
        )
        self.risk_model = MLModelVersion.objects.create(
            name="Risk model", version="risk-api-v1", model_type=ModelType.FAILURE_PREDICTION,
            architecture="GRU", training_dataset="test", trained_at=timezone.now(),
        )
        self.now = timezone.now()

    def create_alert(
        self,
        *,
        resource=None,
        alert_type=AlertType.FAILURE_RISK,
        severity=AlertSeverity.HIGH,
        alert_status=AlertStatus.OPEN,
        actor=None,
    ):
        kwargs = {
            "resource": resource or self.resource,
            "alert_type": alert_type,
            "severity": severity,
            "status": alert_status,
            "first_seen_at": self.now - timedelta(hours=2),
            "last_seen_at": self.now - timedelta(hours=1),
        }
        if alert_status == AlertStatus.ACKNOWLEDGED:
            kwargs.update(acknowledged_at=self.now - timedelta(minutes=30), acknowledged_by=actor)
        elif alert_status == AlertStatus.RESOLVED:
            kwargs.update(
                resolved_at=self.now,
                resolution_source="AUTO",
                consecutive_clear_count=2,
            )
        return Alert.objects.create(**kwargs)

    def test_all_roles_can_list_and_retrieve_alerts(self):
        alert = self.create_alert()
        for role, user in self.users.items():
            with self.subTest(role=role):
                self.client.force_authenticate(user=user)
                listed = self.client.get("/api/alerts/")
                detail = self.client.get(f"/api/alerts/{alert.pk}/")
                self.assertEqual(listed.status_code, status.HTTP_200_OK)
                self.assertEqual(listed.data["count"], 1)
                self.assertEqual(detail.status_code, status.HTTP_200_OK)
                self.assertEqual(detail.data["resource"]["identifier"], self.resource.identifier)
                self.assertNotIn("values", detail.data)

    def test_alert_list_filters_and_pagination(self):
        risk = self.create_alert()
        other_resource = Resource.objects.create(
            name="Second drive", identifier="ALERT-API-2", resource_type=ResourceType.DISK,
        )
        anomaly = self.create_alert(
            resource=other_resource,
            alert_type=AlertType.ANOMALY,
            alert_status=AlertStatus.ACKNOWLEDGED,
            actor=self.users[Role.IT_PRO],
        )
        resolved = self.create_alert(
            resource=Resource.objects.create(
                name="Third drive", identifier="ALERT-API-3", resource_type=ResourceType.DISK,
            ),
            severity=AlertSeverity.CRITICAL,
            alert_status=AlertStatus.RESOLVED,
        )
        self.client.force_authenticate(user=self.users[Role.OPERATOR])

        response = self.client.get(
            "/api/alerts/",
            {
                "status": AlertStatus.OPEN,
                "alert_type": AlertType.FAILURE_RISK,
                "severity": AlertSeverity.HIGH,
                "resource": str(self.resource.pk),
                "page_size": 1,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], str(risk.pk))
        self.assertEqual(anomaly.status, AlertStatus.ACKNOWLEDGED)
        self.assertEqual(resolved.status, AlertStatus.RESOLVED)

        for index in range(2):
            resource = Resource.objects.create(
                name=f"Page drive {index}", identifier=f"ALERT-PAGE-{index}", resource_type=ResourceType.DISK,
            )
            self.create_alert(resource=resource, alert_type=AlertType.ANOMALY)
        page = self.client.get("/api/alerts/", {"page_size": 1})
        self.assertEqual(page.data["count"], 5)
        self.assertEqual(len(page.data["results"]), 1)
        self.assertIsNotNone(page.data["next"])

    def test_alert_list_rejects_invalid_filters(self):
        self.client.force_authenticate(user=self.users[Role.IT_PRO])
        for params in (
            {"status": "BROKEN"},
            {"alert_type": "OTHER"},
            {"severity": "LOW"},
            {"resource": "not-a-uuid"},
        ):
            with self.subTest(params=params):
                response = self.client.get("/api/alerts/", params)
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unread_count_counts_open_alerts_only_for_authenticated_roles(self):
        self.create_alert(alert_status=AlertStatus.OPEN)
        self.create_alert(
            resource=Resource.objects.create(
                name="Acknowledged drive", identifier="ALERT-ACK", resource_type=ResourceType.DISK,
            ),
            alert_type=AlertType.ANOMALY,
            alert_status=AlertStatus.ACKNOWLEDGED,
            actor=self.users[Role.SYSADMIN],
        )
        self.create_alert(
            resource=Resource.objects.create(
                name="Resolved drive", identifier="ALERT-RES", resource_type=ResourceType.DISK,
            ),
            alert_status=AlertStatus.RESOLVED,
        )
        for role, user in self.users.items():
            with self.subTest(role=role):
                self.client.force_authenticate(user=user)
                response = self.client.get("/api/alerts/unread-count/")
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertEqual(response.data, {"count": 1})

    def test_acknowledge_records_actor_timestamp_and_audit_and_is_idempotent(self):
        alert = self.create_alert()
        self.client.force_authenticate(user=self.users[Role.IT_PRO])

        response = self.client.post(f"/api/alerts/{alert.pk}/acknowledge/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], AlertStatus.ACKNOWLEDGED)
        self.assertEqual(response.data["acknowledged_by"], self.users[Role.IT_PRO].username)
        self.assertIsNotNone(response.data["acknowledged_at"])
        event_count = AuditLog.objects.filter(resource_type="Alert", resource_id=str(alert.pk)).count()

        repeated = self.client.post(f"/api/alerts/{alert.pk}/acknowledge/")
        self.assertEqual(repeated.status_code, status.HTTP_200_OK)
        self.assertEqual(AuditLog.objects.filter(resource_type="Alert", resource_id=str(alert.pk)).count(), event_count)
        event = AuditLog.objects.get(resource_type="Alert", resource_id=str(alert.pk))
        self.assertEqual(event.action, ActionType.UPDATE)
        self.assertEqual(event.details["action"], "acknowledge")

    def test_sysadmin_can_manually_resolve_and_resolution_is_distinct_from_automatic(self):
        alert = self.create_alert()
        self.client.force_authenticate(user=self.users[Role.SYSADMIN])

        response = self.client.post(f"/api/alerts/{alert.pk}/resolve/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], AlertStatus.RESOLVED)
        self.assertEqual(response.data["resolution_source"], "USER")
        self.assertEqual(response.data["resolved_by"], self.users[Role.SYSADMIN].username)
        self.assertIsNotNone(response.data["resolved_at"])
        event = AuditLog.objects.get(resource_type="Alert", resource_id=str(alert.pk))
        self.assertEqual(event.details["action"], "resolve")

    def test_itpro_can_manually_resolve_and_sysadmin_can_acknowledge(self):
        resolve_alert = self.create_alert()
        acknowledge_alert = self.create_alert(
            resource=Resource.objects.create(
                name="Second role drive", identifier="ALERT-ROLE-2", resource_type=ResourceType.DISK,
            ),
        )

        self.client.force_authenticate(user=self.users[Role.IT_PRO])
        resolved = self.client.post(f"/api/alerts/{resolve_alert.pk}/resolve/")
        self.client.force_authenticate(user=self.users[Role.SYSADMIN])
        acknowledged = self.client.post(f"/api/alerts/{acknowledge_alert.pk}/acknowledge/")

        self.assertEqual(resolved.status_code, status.HTTP_200_OK)
        self.assertEqual(resolved.data["resolution_source"], "USER")
        self.assertEqual(acknowledged.status_code, status.HTTP_200_OK)
        self.assertEqual(acknowledged.data["status"], AlertStatus.ACKNOWLEDGED)

    def test_operators_are_forbidden_and_unauthenticated_users_are_rejected(self):
        alert = self.create_alert()
        for action in ("acknowledge", "resolve"):
            self.client.force_authenticate(user=None)
            response = self.client.post(f"/api/alerts/{alert.pk}/{action}/")
            self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

            self.client.force_authenticate(user=self.users[Role.OPERATOR])
            response = self.client.post(f"/api/alerts/{alert.pk}/{action}/")
            self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        alert.refresh_from_db()
        self.assertEqual(alert.status, AlertStatus.OPEN)

    def test_invalid_transitions_and_resolved_history(self):
        alert = self.create_alert(alert_status=AlertStatus.RESOLVED)
        self.client.force_authenticate(user=self.users[Role.IT_PRO])

        acknowledge = self.client.post(f"/api/alerts/{alert.pk}/acknowledge/")
        resolve = self.client.post(f"/api/alerts/{alert.pk}/resolve/")
        detail = self.client.get(f"/api/alerts/{alert.pk}/")
        self.assertEqual(acknowledge.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(resolve.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(detail.status_code, status.HTTP_200_OK)
        self.assertEqual(detail.data["resolution_source"], "AUTO")

    def test_invalid_and_nonexistent_alert_ids_return_not_found(self):
        self.client.force_authenticate(user=self.users[Role.OPERATOR])
        invalid = self.client.get("/api/alerts/not-a-uuid/")
        missing_id = uuid.uuid4()
        missing = self.client.get(f"/api/alerts/{missing_id}/")
        missing_action = self.client.post(f"/api/alerts/{missing_id}/acknowledge/")
        self.assertEqual(invalid.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(missing.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(missing_action.status_code, status.HTTP_403_FORBIDDEN)

        self.client.force_authenticate(user=self.users[Role.IT_PRO])
        missing_authorized_action = self.client.post(f"/api/alerts/{missing_id}/acknowledge/")
        invalid_authorized_action = self.client.post("/api/alerts/not-a-uuid/acknowledge/")
        self.assertEqual(missing_authorized_action.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(invalid_authorized_action.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(invalid_authorized_action.data, {"detail": "Alert not found."})

    def test_audit_failure_rolls_back_alert_action_and_returns_safe_error(self):
        alert = self.create_alert()
        self.client.force_authenticate(user=self.users[Role.IT_PRO])
        with patch("alerts.views.log_action", side_effect=IntegrityError("private database detail")):
            response = self.client.post(f"/api/alerts/{alert.pk}/acknowledge/")

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertNotIn("private database detail", str(response.data))
        alert.refresh_from_db()
        self.assertEqual(alert.status, AlertStatus.OPEN)
        self.assertIsNone(alert.acknowledged_at)
        self.assertFalse(AuditLog.objects.filter(resource_type="Alert", resource_id=str(alert.pk)).exists())

    def test_manual_resolution_audit_failure_rolls_back_transition(self):
        alert = self.create_alert()
        self.client.force_authenticate(user=self.users[Role.IT_PRO])
        with patch("alerts.views.log_action", side_effect=IntegrityError("private database detail")):
            response = self.client.post(f"/api/alerts/{alert.pk}/resolve/")

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertNotIn("private database detail", str(response.data))
        alert.refresh_from_db()
        self.assertEqual(alert.status, AlertStatus.OPEN)
        self.assertIsNone(alert.resolved_at)
        self.assertIsNone(alert.resolved_by_id)
        self.assertEqual(alert.resolution_source, "")
