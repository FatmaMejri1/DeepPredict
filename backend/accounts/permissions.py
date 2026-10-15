from rest_framework.permissions import SAFE_METHODS, BasePermission

from .models import Role


class IsSysAdmin(BasePermission):
    """Only system administrators."""

    message = "Only a system administrator can perform this action."

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.role == Role.SYSADMIN)


class IsSysAdminOrReadOnly(BasePermission):
    """Any logged-in user can read; only system administrators can write."""

    message = "Only a system administrator can modify this data."

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if request.method in SAFE_METHODS:
            return True
        return user.role == Role.SYSADMIN
