from django.contrib import admin
from django.test import Client, TestCase
from django.urls import reverse

from accounts.models import Role, User
from audit.models import AuditLog
from infrastructure.models import Resource
from ml_models.models import MLModelVersion
from monitoring.models import Metric
from predictions.models import Prediction


class DjangoAdminAuthorizationTests(TestCase):
    password = "TestOnly!Password123"

    def make_user(self, username, role, *, is_staff=True, is_active=True, is_superuser=False):
        return User.objects.create_user(
            username=username,
            email=f"{username}@example.test",
            password=self.password,
            role=role,
            is_staff=is_staff,
            is_active=is_active,
            is_superuser=is_superuser,
        )

    def assert_admin_denied(self, user):
        client = Client()
        if user.is_active:
            self.assertTrue(client.login(username=user.username, password=self.password))
        else:
            self.assertFalse(client.login(username=user.username, password=self.password))

        for path in ("/admin/", reverse("admin:accounts_user_changelist")):
            response = client.get(path)
            self.assertEqual(response.status_code, 302)
            self.assertIn(reverse("admin:login"), response["Location"])

    def test_active_sysadmin_staff_can_access_admin(self):
        user = self.make_user("sysadmin_staff", Role.SYSADMIN, is_superuser=True)
        client = Client()
        self.assertTrue(client.login(username=user.username, password=self.password))

        self.assertEqual(client.get("/admin/").status_code, 200)
        self.assertEqual(client.get(reverse("admin:accounts_user_changelist")).status_code, 200)

    def test_active_sysadmin_staff_without_superuser_status_can_access_admin_landing_page(self):
        user = self.make_user(
            "sysadmin_staff_non_superuser",
            Role.SYSADMIN,
            is_staff=True,
            is_active=True,
            is_superuser=False,
        )
        client = Client()
        self.assertTrue(client.login(username=user.username, password=self.password))

        self.assertEqual(client.get("/admin/").status_code, 200)

    def test_active_it_pro_staff_cannot_access_admin(self):
        user = self.make_user("itpro_staff", Role.IT_PRO)
        self.assert_admin_denied(user)

    def test_active_operator_staff_cannot_access_admin(self):
        user = self.make_user("operator_staff", Role.OPERATOR)
        self.assert_admin_denied(user)

    def test_sysadmin_without_staff_status_cannot_access_admin(self):
        user = self.make_user("sysadmin_nonstaff", Role.SYSADMIN, is_staff=False)
        self.assert_admin_denied(user)

    def test_inactive_sysadmin_staff_cannot_access_admin(self):
        user = self.make_user("inactive_sysadmin", Role.SYSADMIN, is_active=False)
        self.assert_admin_denied(user)

    def test_unauthenticated_request_is_redirected_to_admin_login(self):
        response = Client().get("/admin/")
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("admin:login"), response["Location"])

    def test_existing_model_registrations_remain_on_the_default_site(self):
        for model in (User, Resource, Metric, Prediction, MLModelVersion, AuditLog):
            with self.subTest(model=model.__name__):
                self.assertTrue(admin.site.is_registered(model))
