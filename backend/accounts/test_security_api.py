from datetime import timedelta
import secrets

from django.core.cache import cache
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from .models import Role, User


def credential(prefix="Security#"):
    return f"{prefix}{secrets.token_urlsafe(18)}"


class TokenRevocationAPITests(APITestCase):
    def setUp(self):
        cache.clear()
        self.admin_password = credential("Admin#")
        self.user_password = credential("User#")
        self.new_password = credential("Changed#")
        self.admin = User.objects.create_user(
            username="security-admin", email="security-admin@example.test",
            password=self.admin_password, role=Role.SYSADMIN,
        )
        self.user = User.objects.create_user(
            username="security-user", email="security-user@example.test",
            password=self.user_password, role=Role.IT_PRO,
        )

    def login(self, username, password):
        response = self.client.post(
            "/api/auth/login/", {"username": username, "password": password}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        return response.data

    def authorize(self, access):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

    def test_logout_blacklists_owned_refresh_but_does_not_revoke_access_token(self):
        tokens = self.login("security-user", self.user_password)
        self.authorize(tokens["access"])

        response = self.client.post("/api/auth/logout/", {"refresh": tokens["refresh"]}, format="json")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(
            self.client.post("/api/auth/refresh/", {"refresh": tokens["refresh"]}, format="json").status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
        # SimpleJWT's blacklist only covers refresh tokens; this access token
        # remains usable until its 15-minute expiry.
        self.assertEqual(self.client.get("/api/auth/me/").status_code, status.HTTP_200_OK)

    def test_logout_rejects_missing_malformed_expired_and_foreign_refresh_tokens(self):
        user_tokens = self.login("security-user", self.user_password)
        admin_tokens = self.login("security-admin", self.admin_password)
        self.authorize(admin_tokens["access"])

        self.assertEqual(self.client.post("/api/auth/logout/", {}, format="json").status_code, 400)
        self.assertEqual(
            self.client.post("/api/auth/logout/", {"refresh": "not-a-jwt"}, format="json").status_code,
            400,
        )
        self.assertEqual(
            self.client.post("/api/auth/logout/", {"refresh": user_tokens["refresh"]}, format="json").status_code,
            400,
        )

        expired = RefreshToken.for_user(self.admin)
        expired.set_exp(from_time=timezone.now() - timedelta(seconds=5), lifetime=timedelta(seconds=-1))
        self.assertEqual(
            self.client.post("/api/auth/logout/", {"refresh": str(expired)}, format="json").status_code,
            400,
        )

        self.assertEqual(
            self.client.post("/api/auth/logout/", {"refresh": admin_tokens["refresh"]}, format="json").status_code,
            status.HTTP_204_NO_CONTENT,
        )
        self.assertEqual(
            self.client.post("/api/auth/logout/", {"refresh": admin_tokens["refresh"]}, format="json").status_code,
            400,
        )

    def test_password_change_revokes_existing_access_and_refresh_tokens(self):
        tokens = self.login("security-user", self.user_password)
        self.authorize(tokens["access"])

        response = self.client.post(
            "/api/auth/change-password/",
            {"old_password": self.user_password, "new_password": self.new_password},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.get("/api/auth/me/").status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(
            self.client.post("/api/auth/refresh/", {"refresh": tokens["refresh"]}, format="json").status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_admin_password_reset_revokes_target_access_and_refresh_tokens(self):
        user_tokens = self.login("security-user", self.user_password)
        admin_tokens = self.login("security-admin", self.admin_password)
        self.authorize(admin_tokens["access"])

        response = self.client.post(
            f"/api/users/{self.user.pk}/set-password/", {"password": self.new_password}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.authorize(user_tokens["access"])
        self.assertEqual(self.client.get("/api/auth/me/").status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(
            self.client.post("/api/auth/refresh/", {"refresh": user_tokens["refresh"]}, format="json").status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_deactivation_rejects_previously_issued_access_and_refresh_tokens(self):
        user_tokens = self.login("security-user", self.user_password)
        admin_tokens = self.login("security-admin", self.admin_password)
        self.authorize(admin_tokens["access"])

        response = self.client.post(f"/api/users/{self.user.pk}/deactivate/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.authorize(user_tokens["access"])
        self.assertEqual(self.client.get("/api/auth/me/").status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(
            self.client.post("/api/auth/refresh/", {"refresh": user_tokens["refresh"]}, format="json").status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_invalid_and_expired_access_and_refresh_tokens_are_rejected(self):
        self.authorize("not-a-jwt")
        self.assertEqual(self.client.get("/api/auth/me/").status_code, status.HTTP_401_UNAUTHORIZED)

        expired_access = AccessToken.for_user(self.user)
        expired_access.set_exp(from_time=timezone.now() - timedelta(seconds=5), lifetime=timedelta(seconds=-1))
        self.authorize(str(expired_access))
        self.assertEqual(self.client.get("/api/auth/me/").status_code, status.HTTP_401_UNAUTHORIZED)

        self.assertEqual(
            self.client.post("/api/auth/refresh/", {"refresh": "not-a-jwt"}, format="json").status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
        expired_refresh = RefreshToken.for_user(self.user)
        expired_refresh.set_exp(from_time=timezone.now() - timedelta(seconds=5), lifetime=timedelta(seconds=-1))
        self.assertEqual(
            self.client.post("/api/auth/refresh/", {"refresh": str(expired_refresh)}, format="json").status_code,
            status.HTTP_401_UNAUTHORIZED,
        )


class RoleAuthorizationAPITests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="role-admin", email="role-admin@example.test", password=credential(), role=Role.SYSADMIN
        )
        self.it_pro = User.objects.create_user(
            username="role-itpro", email="role-itpro@example.test", password=credential(), role=Role.IT_PRO
        )
        self.operator = User.objects.create_user(
            username="role-operator", email="role-operator@example.test", password=credential(), role=Role.OPERATOR
        )
        self.victim = User.objects.create_user(
            username="role-victim", email="role-victim@example.test", password=credential(), role=Role.SYSADMIN
        )

    def test_operator_cannot_generate_predictions_or_upload_telemetry(self):
        self.client.force_authenticate(self.operator)
        self.assertEqual(
            self.client.post("/api/predictions/predict/", {}, format="json").status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.assertEqual(
            self.client.post("/api/telemetry/upload/", {"readings": [{}]}, format="json").status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_itpro_and_operator_cannot_access_or_mutate_users_by_uuid(self):
        actions = [
            ("get", f"/api/users/{self.victim.pk}/", None),
            ("post", "/api/users/", {"username": "attack", "email": "attack@example.test",
                                      "password": credential(), "role": "SYSADMIN",
                                      "is_staff": True, "is_superuser": True}),
            ("patch", f"/api/users/{self.victim.pk}/", {"role": "SYSADMIN", "is_staff": True,
                                                         "is_superuser": True}),
            ("post", f"/api/users/{self.victim.pk}/activate/", {}),
            ("post", f"/api/users/{self.victim.pk}/deactivate/", {}),
            ("post", f"/api/users/{self.victim.pk}/set-password/", {"password": credential()}),
        ]
        for user in (self.it_pro, self.operator):
            self.client.force_authenticate(user)
            for method, url, payload in actions:
                with self.subTest(role=user.role, method=method, url=url):
                    response = getattr(self.client, method)(url, payload, format="json") if payload is not None else getattr(self.client, method)(url)
                    self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        self.victim.refresh_from_db()
        self.assertEqual(self.victim.role, Role.SYSADMIN)
        self.assertFalse(self.victim.is_staff)
        self.assertFalse(self.victim.is_superuser)
        self.assertTrue(User.objects.filter(username="attack").exists() is False)
