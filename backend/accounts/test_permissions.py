import secrets
from django.test import TestCase
from rest_framework.test import APIRequestFactory

from accounts.models import Role, User
from accounts.permissions import (
    IsSysAdmin,
    IsSysAdminOrReadOnly,
    IsITProOrSysAdmin,
    IsOperatorReadOnly,
)


class PermissionTests(TestCase):

    def setUp(self):
        self.factory = APIRequestFactory()
        test_credential = f"Auth#{secrets.token_urlsafe(16)}"

        self.admin = User.objects.create_user(
            username="permission_admin",
            email="permission_admin@example.com",
            password=test_credential,
            role=Role.SYSADMIN,
        )

        self.pro = User.objects.create_user(
            username="permission_pro",
            email="permission_pro@example.com",
            password=test_credential,
            role=Role.IT_PRO,
        )

        self.operator = User.objects.create_user(
            username="permission_operator",
            email="permission_operator@example.com",
            password=test_credential,
            role=Role.OPERATOR,
        )

    def check_permission(self, permission_class, method, user):
        request = getattr(self.factory, method.lower())("/")
        request.user = user
        return permission_class().has_permission(request, None)

    def test_is_sysadmin(self):
        self.assertTrue(
            self.check_permission(IsSysAdmin, "GET", self.admin)
        )
        self.assertFalse(
            self.check_permission(IsSysAdmin, "GET", self.pro)
        )
        self.assertFalse(
            self.check_permission(IsSysAdmin, "GET", self.operator)
        )

        from django.contrib.auth.models import AnonymousUser

        self.assertFalse(
            self.check_permission(IsSysAdmin, "GET", AnonymousUser())
        )

    def test_sysadmin_or_read_only(self):
        from django.contrib.auth.models import AnonymousUser

        for user in (self.admin, self.pro, self.operator):
            with self.subTest(user=user.username):
                self.assertTrue(
                    self.check_permission(IsSysAdminOrReadOnly, "GET", user)
                )

        self.assertTrue(
            self.check_permission(IsSysAdminOrReadOnly, "POST", self.admin)
        )
        self.assertFalse(
            self.check_permission(IsSysAdminOrReadOnly, "POST", self.pro)
        )
        self.assertFalse(
            self.check_permission(IsSysAdminOrReadOnly, "DELETE", self.operator)
        )
        self.assertFalse(
            self.check_permission(
                IsSysAdminOrReadOnly, "GET", AnonymousUser()
            )
        )

    def test_it_pro_or_sysadmin(self):
        self.assertTrue(
            self.check_permission(IsITProOrSysAdmin, "POST", self.admin)
        )
        self.assertTrue(
            self.check_permission(IsITProOrSysAdmin, "POST", self.pro)
        )
        self.assertFalse(
            self.check_permission(IsITProOrSysAdmin, "POST", self.operator)
        )

        from django.contrib.auth.models import AnonymousUser

        self.assertFalse(
            self.check_permission(
                IsITProOrSysAdmin, "GET", AnonymousUser()
            )
        )

    def test_operator_read_only(self):
        from django.contrib.auth.models import AnonymousUser

        for user in (self.admin, self.pro, self.operator):
            with self.subTest(user=user.username):
                self.assertTrue(
                    self.check_permission(IsOperatorReadOnly, "GET", user)
                )

        self.assertTrue(
            self.check_permission(IsOperatorReadOnly, "POST", self.admin)
        )
        self.assertTrue(
            self.check_permission(IsOperatorReadOnly, "POST", self.pro)
        )
        self.assertFalse(
            self.check_permission(IsOperatorReadOnly, "POST", self.operator)
        )
        self.assertFalse(
            self.check_permission(
                IsOperatorReadOnly, "GET", AnonymousUser()
            )
        )
