from datetime import datetime, timezone
from unittest.mock import patch

from django.contrib import admin
from django.db import IntegrityError
from django.test import RequestFactory, TestCase

from accounts.models import Role, User
from audit.models import ActionType, AuditLog
from infrastructure.models import Resource, ResourceType
from ml_models.models import MLModelVersion, ModelType
from monitoring.models import Metric
from predictions.models import Prediction


class AuditedAdminTests(TestCase):
    def setUp(self):
        self.request = RequestFactory().post("/admin/")
        self.actor = User.objects.create_superuser(
            username="admin_audit_test", email="admin_audit_test@example.com", password="test-password"
        )
        self.request.user = self.actor
        self.resource = Resource.objects.create(
            name="Admin test drive", identifier="ADMIN-AUDIT", resource_type=ResourceType.DISK
        )
        self.model_version = MLModelVersion.objects.create(
            name="Risk", model_type=ModelType.FAILURE_PREDICTION, architecture="GRU",
            version="test-v1", training_dataset="test", trained_at=datetime.now(timezone.utc),
        )

    def test_admin_models_audit_create_update_and_individual_delete(self):
        resource_admin = admin.site._registry[Resource]
        self.resource.name = "Updated drive name"
        resource_admin.save_model(self.request, self.resource, None, True)
        self.assertTrue(AuditLog.objects.filter(
            resource_type="Resource", resource_id=str(self.resource.pk), action=ActionType.UPDATE
        ).exists())

        user = User.objects.create_user(
            username="admin-managed-user", email="admin-managed@example.com", password="test-password"
        )
        user_admin = admin.site._registry[User]
        user.first_name = "Updated"
        user_admin.save_model(self.request, user, None, True)
        self.assertTrue(AuditLog.objects.filter(
            resource_type="User", resource_id=str(user.pk), action=ActionType.UPDATE
        ).exists())

        metric = Metric(resource=self.resource, timestamp=datetime.now(timezone.utc), values={"smart_5_raw": 1})
        metric_admin = admin.site._registry[Metric]
        metric_admin.save_model(self.request, metric, None, False)
        metric.source = "changed"
        metric_admin.save_model(self.request, metric, None, True)
        self.assertEqual(
            list(AuditLog.objects.filter(resource_type="Metric").values_list("action", flat=True)),
            [ActionType.UPDATE, ActionType.CREATE],
        )
        self.assertEqual(AuditLog.objects.filter(resource_type="Metric").first().details,
                         {"action": "update", "source": "django_admin"})

        risk = Prediction.objects.create(
            resource=self.resource, model_version=self.model_version, score=0.5,
            risk_level="MEDIUM", horizon_days=7,
            window_start=datetime.now(timezone.utc), window_end=datetime.now(timezone.utc),
        )
        prediction_admin = admin.site._registry[Prediction]
        prediction_admin.delete_model(self.request, risk)
        self.assertTrue(AuditLog.objects.filter(resource_type="Prediction", action=ActionType.DELETE).exists())

        model_admin = admin.site._registry[MLModelVersion]
        model_admin.save_model(self.request, self.model_version, None, True)
        self.assertTrue(AuditLog.objects.filter(
            resource_type="MLModelVersion", action=ActionType.CONFIG_CHANGE
        ).exists())

    def test_bulk_delete_is_audited_and_rolls_back_when_audit_fails(self):
        another = Resource.objects.create(
            name="Bulk delete drive", identifier="ADMIN-BULK", resource_type=ResourceType.DISK
        )
        resource_admin = admin.site._registry[Resource]
        resource_admin.delete_queryset(self.request, Resource.objects.filter(pk=another.pk))
        self.assertFalse(Resource.objects.filter(pk=another.pk).exists())
        self.assertTrue(AuditLog.objects.filter(
            resource_type="Resource", resource_id=str(another.pk), action=ActionType.DELETE
        ).exists())

        keep = Resource.objects.create(
            name="Rollback drive", identifier="ADMIN-ROLLBACK", resource_type=ResourceType.DISK
        )
        with patch("audit.admin.log_action", side_effect=IntegrityError("audit unavailable")):
            with self.assertRaises(IntegrityError):
                resource_admin.delete_queryset(self.request, Resource.objects.filter(pk=keep.pk))
        self.assertTrue(Resource.objects.filter(pk=keep.pk).exists())

    def test_ml_model_admin_delete_uses_configuration_action(self):
        model_admin = admin.site._registry[MLModelVersion]
        model_admin.delete_model(self.request, self.model_version)
        event = AuditLog.objects.get(resource_type="MLModelVersion", action=ActionType.CONFIG_CHANGE)
        self.assertEqual(event.details["action"], "delete")
