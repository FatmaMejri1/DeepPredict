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


class IsITProOrSysAdmin(BasePermission):
    """IT Professionals and System Administrators can perform operations; Operators cannot."""

    message = "IT Professional or System Administrator role is required."

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user and user.is_authenticated and user.role in (Role.SYSADMIN, Role.IT_PRO)
        )


class IsOperatorReadOnly(BasePermission):
    """Operators have read-only access. Write operations require IT_PRO or SYSADMIN."""

    message = "Operators have read-only access."

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if request.method in SAFE_METHODS:
            return True
        return user.role in (Role.SYSADMIN, Role.IT_PRO)
