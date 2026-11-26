from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import Role
from audit.models import ActionType, AuditLog


User = get_user_model()


class AuditLogAPITests(APITestCase):
    url = "/api/audit-logs/"

    def setUp(self):
        self.sysadmin = User.objects.create_user(
            username="audit-admin", email="audit-admin@example.com", password="test-password",
            role=Role.SYSADMIN, is_staff=True,
        )
        self.it_pro = User.objects.create_user(
            username="audit-itpro", email="audit-itpro@example.com", password="test-password",
            role=Role.IT_PRO, is_staff=True,
        )
        self.operator = User.objects.create_user(
            username="audit-operator", email="audit-operator@example.com", password="test-password",
            role=Role.OPERATOR, is_staff=True,
        )

    def create_log(self, *, user=None, username="", action=ActionType.CREATE, resource_id="resource-1"):
        return AuditLog.objects.create(
            user=user,
            username=username,
            action=action,
            resource_type="Resource",
            resource_id=resource_id,
            ip_address="192.0.2.10",
            details={"sensitive": "must not be returned"},
        )

    def test_sysadmin_can_read_safe_fields_only_and_endpoint_is_read_only(self):
        self.create_log(user=self.sysadmin, resource_id="resource-1")
        self.create_log(username="deleted-account", action=ActionType.DELETE)
        self.client.force_authenticate(self.sysadmin)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)
        entry = response.data["results"][0]
        self.assertEqual(set(entry), {
            "id", "timestamp", "username", "action", "resource_type", "resource_id",
        })
        self.assertNotIn("details", entry)
        self.assertNotIn("ip_address", entry)
        self.assertEqual(entry["username"], "deleted-account")
        for method in ("post", "put", "patch", "delete"):
            with self.subTest(method=method):
                response = getattr(self.client, method)(self.url, {}, format="json")
                self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertEqual(AuditLog.objects.count(), 2)

    def test_it_pro_and_operator_are_forbidden_even_when_staff(self):
        self.create_log(user=self.sysadmin)
        for user in (self.it_pro, self.operator):
            with self.subTest(role=user.role):
                self.client.force_authenticate(user)
                self.assertEqual(self.client.get(self.url).status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_request_is_rejected(self):
        self.assertEqual(self.client.get(self.url).status_code, status.HTTP_401_UNAUTHORIZED)

    def test_username_action_date_filters_and_pagination(self):
        self.create_log(user=self.sysadmin, action=ActionType.CREATE, resource_id="one")
        self.create_log(user=self.it_pro, action=ActionType.UPDATE, resource_id="two")
        self.create_log(username="removed-user", action=ActionType.CREATE, resource_id="three")
        self.client.force_authenticate(self.sysadmin)
        today = timezone.localdate().isoformat()

        filtered = self.client.get(self.url, {
            "username": "audit-admin", "action": ActionType.CREATE,
            "date_from": today, "date_to": today,
        })
        self.assertEqual(filtered.status_code, status.HTTP_200_OK)
        self.assertEqual(filtered.data["count"], 1)
        self.assertEqual(filtered.data["results"][0]["resource_id"], "one")

        first_page = self.client.get(self.url, {"date_from": today, "date_to": today, "page_size": 1})
        self.assertEqual(first_page.data["count"], 3)
        self.assertEqual(len(first_page.data["results"]), 1)
        self.assertIsNone(first_page.data["previous"])
        self.assertIsNotNone(first_page.data["next"])
        second_page = self.client.get(self.url, {
            "date_from": today, "date_to": today, "page_size": 1, "page": 2,
        })
        self.assertEqual(len(second_page.data["results"]), 1)
        self.assertIsNotNone(second_page.data["previous"])

    def test_invalid_action_and_date_range_return_400(self):
        self.client.force_authenticate(self.sysadmin)
        self.assertEqual(
            self.client.get(self.url, {"action": "NOT_AN_ACTION"}).status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(
            self.client.get(self.url, {"date_from": "2026-15-60"}).status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(
            self.client.get(self.url, {"date_from": "2026-11-20", "date_to": "2026-11-19"}).status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_non_staff_sysadmin_is_forbidden(self):
        non_staff = User.objects.create_user(
            username="role-only-admin", email="role-only@example.com", password="test-password",
            role=Role.SYSADMIN, is_staff=False,
        )
        self.client.force_authenticate(non_staff)
        self.assertEqual(self.client.get(self.url).status_code, status.HTTP_403_FORBIDDEN)

    def test_inactive_sysadmin_is_forbidden(self):
        inactive = User.objects.create_user(
            username="inactive-admin", email="inactive-admin@example.com", password="test-password",
            role=Role.SYSADMIN, is_staff=True, is_active=False,
        )
        self.client.force_authenticate(inactive)
        self.assertEqual(self.client.get(self.url).status_code, status.HTTP_403_FORBIDDEN)

    def test_missing_actor_uses_a_safe_username_fallback(self):
        self.create_log(username="")
        self.client.force_authenticate(self.sysadmin)
        response = self.client.get(self.url)
        self.assertEqual(response.data["results"][0]["username"], "Unknown")
