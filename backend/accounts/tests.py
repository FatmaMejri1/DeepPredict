from django.core.cache import cache
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Role, User

PASSWORD = "Str0ng!Pass#1"


class AccountsTests(APITestCase):
    def setUp(self):
        cache.clear()  # reset the login rate limit between tests
        self.admin = User.objects.create_user(
            username="admin1", email="admin1@example.com",
            password=PASSWORD, role=Role.SYSADMIN,
        )
        self.pro = User.objects.create_user(
            username="pro1", email="pro1@example.com",
            password=PASSWORD, role=Role.IT_PRO,
        )

    def login(self, identifier, password=PASSWORD):
        return self.client.post(
            "/api/auth/login/", {"username": identifier, "password": password}, format="json"
        )

    # ---- login and tokens ----
    def test_login_with_username(self):
        response = self.login("admin1")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        self.assertEqual(response.data["user"]["role"], "SYSADMIN")

    def test_login_with_email(self):
        response = self.login("PRO1@example.com")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["user"]["username"], "pro1")

    def test_login_wrong_password(self):
        self.assertEqual(self.login("admin1", "wrong").status_code, status.HTTP_401_UNAUTHORIZED)

    def test_inactive_user_cannot_login(self):
        self.pro.is_active = False
        self.pro.save()
        self.assertEqual(self.login("pro1").status_code, status.HTTP_401_UNAUTHORIZED)

    def test_refresh_token(self):
        refresh = self.login("admin1").data["refresh"]
        response = self.client.post("/api/auth/refresh/", {"refresh": refresh}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)

    # ---- current user ----
    def test_me_requires_authentication(self):
        self.assertEqual(self.client.get("/api/auth/me/").status_code, status.HTTP_401_UNAUTHORIZED)

    def test_me_with_real_token(self):
        access = self.login("pro1").data["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        response = self.client.get("/api/auth/me/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["role"], "IT_PRO")

    # ---- permissions ----
    def test_it_pro_cannot_list_users(self):
        self.client.force_authenticate(self.pro)
        self.assertEqual(self.client.get("/api/users/").status_code, status.HTTP_403_FORBIDDEN)

    def test_it_pro_cannot_create_users(self):
        self.client.force_authenticate(self.pro)
        response = self.client.post("/api/users/", {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_sysadmin_can_list_users(self):
        self.client.force_authenticate(self.admin)
        response = self.client.get("/api/users/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)

    def test_filter_users_by_role(self):
        self.client.force_authenticate(self.admin)
        response = self.client.get("/api/users/?role=IT_PRO")
        self.assertEqual(response.data["count"], 1)

    # ---- user management ----
    def test_sysadmin_creates_user(self):
        self.client.force_authenticate(self.admin)
        payload = {
            "username": "newuser", "email": "New@Example.com",
            "password": "Str0ng!Pass#2", "role": "IT_PRO",
        }
        response = self.client.post("/api/users/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["email"], "new@example.com")
        self.assertNotIn("password", response.data)
        user = User.objects.get(username="newuser")
        self.assertNotEqual(user.password, "Str0ng!Pass#2")  # stored hashed
        self.assertTrue(user.check_password("Str0ng!Pass#2"))

    def test_weak_password_rejected(self):
        self.client.force_authenticate(self.admin)
        payload = {"username": "weak", "email": "weak@example.com", "password": "123"}
        response = self.client.post("/api/users/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_duplicate_email_ignoring_case(self):
        self.client.force_authenticate(self.admin)
        payload = {"username": "dup", "email": "ADMIN1@example.com", "password": "Str0ng!Pass#2"}
        response = self.client.post("/api/users/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cannot_change_own_role(self):
        self.client.force_authenticate(self.admin)
        response = self.client.patch(f"/api/users/{self.admin.id}/", {"role": "IT_PRO"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cannot_deactivate_self(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post(f"/api/users/{self.admin.id}/deactivate/")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_sysadmin_deactivates_another_user(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post(f"/api/users/{self.pro.id}/deactivate/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.pro.refresh_from_db()
        self.assertFalse(self.pro.is_active)

    def test_sysadmin_changes_role_of_another_user(self):
        self.client.force_authenticate(self.admin)
        response = self.client.patch(f"/api/users/{self.pro.id}/", {"role": "SYSADMIN"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.pro.refresh_from_db()
        self.assertEqual(self.pro.role, Role.SYSADMIN)

    def test_delete_is_not_allowed(self):
        self.client.force_authenticate(self.admin)
        response = self.client.delete(f"/api/users/{self.pro.id}/")
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_sysadmin_sets_password_of_another_user(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post(
            f"/api/users/{self.pro.id}/set-password/", {"password": "N3w!Passw0rd#9"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.pro.refresh_from_db()
        self.assertTrue(self.pro.check_password("N3w!Passw0rd#9"))

    # ---- own password ----
    def test_change_own_password(self):
        self.client.force_authenticate(self.pro)
        response = self.client.post(
            "/api/auth/change-password/",
            {"old_password": PASSWORD, "new_password": "N3w!Passw0rd#9"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.client.force_authenticate(None)
        self.assertEqual(self.login("pro1", "N3w!Passw0rd#9").status_code, status.HTTP_200_OK)

    def test_change_password_wrong_old_password(self):
        self.client.force_authenticate(self.pro)
        response = self.client.post(
            "/api/auth/change-password/",
            {"old_password": "wrong", "new_password": "N3w!Passw0rd#9"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # ---- roles at creation ----
    def test_superuser_gets_sysadmin_role(self):
        superuser = User.objects.create_superuser(
            username="root", email="root@example.com", password=PASSWORD
        )
        self.assertEqual(superuser.role, Role.SYSADMIN)

    def test_default_role_is_it_pro(self):
        user = User.objects.create_user(username="plain", email="plain@example.com", password=PASSWORD)
        self.assertEqual(user.role, Role.IT_PRO)