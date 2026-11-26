import secrets
from unittest.mock import patch

from django.core.exceptions import PermissionDenied
from django.db import IntegrityError
from django.test import RequestFactory, TestCase
from django.contrib.auth import get_user_model

from accounts.models import Role
from audit.models import ActionType, AuditLog
from audit.services import log_action

User = get_user_model()


def _generate_test_credential(prefix="Pass#"):
    return f"{prefix}{secrets.token_urlsafe(16)}"


ADMIN_CREDENTIAL = _generate_test_credential("Pass#Admin")
OPERATOR_CREDENTIAL = _generate_test_credential("Pass#Operator")
INVALID_CREDENTIAL = _generate_test_credential("WrongPassword")


class AuditLogTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.admin = User.objects.create_user(
            username="admin_audit", email="admin_audit@example.com", password=ADMIN_CREDENTIAL, role=Role.SYSADMIN
        )
        self.operator = User.objects.create_user(
            username="op_audit", email="op_audit@example.com", password=OPERATOR_CREDENTIAL, role=Role.OPERATOR
        )

    def test_log_action_creates_entry(self):
        log = log_action(
            action=ActionType.CREATE,
            user=self.admin,
            resource_type="Resource",
            resource_id="DISK-001",
            details={"name": "Primary Disk"},
            ip_address="192.168.1.100",
        )
        self.assertIsNotNone(log)
        self.assertEqual(AuditLog.objects.count(), 1)
        self.assertEqual(log.action, ActionType.CREATE)
        self.assertEqual(log.username, "admin_audit")
        self.assertEqual(log.resource_id, "DISK-001")
        self.assertEqual(log.ip_address, "192.168.1.100")
        self.assertEqual(log.details["name"], "Primary Disk")

    @patch("audit.services.AuditLog.objects.create", side_effect=IntegrityError("audit unavailable"))
    def test_required_audit_write_propagates_failure(self, _create):
        with self.assertRaises(IntegrityError):
            log_action(action=ActionType.CREATE, resource_type="Resource", resource_id="DISK-1")

    def test_audit_log_is_immutable_cannot_update(self):
        log = log_action(
            action=ActionType.CONFIG_CHANGE,
            user=self.admin,
            resource_type="Setting",
            resource_id="THRESHOLD",
            details={"old": 0.5, "new": 0.8},
        )
        # Attempt to modify the log
        log.resource_id = "TAMPERED"
        with self.assertRaises(PermissionDenied):
            log.save()

    def test_audit_log_is_immutable_cannot_delete(self):
        log = log_action(
            action=ActionType.DELETE,
            user=self.admin,
            resource_type="User",
            resource_id="USER-123",
        )
        # Attempt to delete the log
        with self.assertRaises(PermissionDenied):
            log.delete()

    def test_login_success_signal_creates_audit_log(self):
        initial_count = AuditLog.objects.count()
        response = self.client.post(
            "/api/auth/login/",
            {"username": "admin_audit", "password": ADMIN_CREDENTIAL},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertGreater(AuditLog.objects.count(), initial_count)
        latest_log = AuditLog.objects.first()
        self.assertEqual(latest_log.action, ActionType.LOGIN_SUCCESS)
        self.assertEqual(latest_log.username, "admin_audit")

    def test_login_failed_signal_creates_audit_log(self):
        initial_count = AuditLog.objects.count()
        response = self.client.post(
            "/api/auth/login/",
            {"username": "admin_audit", "password": INVALID_CREDENTIAL},
            format="json",
        )
        self.assertEqual(response.status_code, 401)
        self.assertGreater(AuditLog.objects.count(), initial_count)
        latest_log = AuditLog.objects.first()
        self.assertEqual(latest_log.action, ActionType.LOGIN_FAILED)
        self.assertEqual(latest_log.details.get("attempted_username"), "admin_audit")

    @patch("audit.services.AuditLog.objects.create", side_effect=IntegrityError("audit unavailable"))
    def test_authentication_audit_failure_is_best_effort(self, _create):
        with self.assertLogs("audit", level="ERROR"):
            response = self.client.post(
                "/api/auth/login/",
                {"username": "admin_audit", "password": ADMIN_CREDENTIAL},
                format="json",
            )
        self.assertEqual(response.status_code, 200)
