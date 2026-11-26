from django.contrib.admin import AdminSite

from .models import Role


class SysAdminAdminSite(AdminSite):
    """Limit Django Admin to active staff users with the SYSADMIN role."""

    def has_permission(self, request):
        user = request.user
        return bool(
            user.is_authenticated
            and user.is_active
            and user.is_staff
            and user.role == Role.SYSADMIN
        )
