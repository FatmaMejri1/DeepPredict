from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from audit.models import ActionType
from audit.services import log_action
from .models import User


class CustomUserAdmin(UserAdmin):
    list_display = ("username", "email", "role", "is_active")
    fieldsets = UserAdmin.fieldsets + (("Role", {"fields": ("role",)}),)
    add_fieldsets = UserAdmin.add_fieldsets + (("Role", {"fields": ("email", "role")}),)

    def save_model(self, request, obj, form, change):
        is_new = not change
        super().save_model(request, obj, form, change)
        log_action(
            action=ActionType.CREATE if is_new else ActionType.UPDATE,
            user=request.user,
            resource_type="User",
            resource_id=str(obj.pk),
            details={
                "username": obj.username,
                "role": obj.role,
                "is_active": obj.is_active,
                "action": "create" if is_new else "update",
            },
            request=request,
        )

    def delete_model(self, request, obj):
        user_id = str(obj.pk)
        username = obj.username
        super().delete_model(request, obj)
        log_action(
            action=ActionType.DELETE,
            user=request.user,
            resource_type="User",
            resource_id=user_id,
            details={"username": username, "action": "delete"},
            request=request,
        )


admin.site.register(User, CustomUserAdmin)