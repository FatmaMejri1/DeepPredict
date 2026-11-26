from django.contrib import admin
from django.db import transaction

from .models import ActionType, AuditLog
from .services import log_action


class AuditLoggedModelAdmin(admin.ModelAdmin):
    """Atomically audit Admin create/update/delete operations, including bulk deletion."""

    audit_configuration_changes = False

    def _audit(self, request, action, obj):
        log_action(
            action=(ActionType.CONFIG_CHANGE if self.audit_configuration_changes else action),
            user=request.user,
            resource_type=obj._meta.object_name,
            resource_id=str(obj.pk),
            details={"action": action.lower(), "source": "django_admin"},
            request=request,
        )

    def save_model(self, request, obj, form, change):
        action = ActionType.UPDATE if change else ActionType.CREATE
        with transaction.atomic():
            super().save_model(request, obj, form, change)
            self._audit(request, action, obj)

    def delete_model(self, request, obj):
        with transaction.atomic():
            super().delete_model(request, obj)
            self._audit(request, ActionType.DELETE, obj)

    def delete_queryset(self, request, queryset):
        # Django's delete_selected action calls delete_queryset rather than
        # delete_model; log each row before deletion in the same transaction.
        with transaction.atomic():
            objects = list(queryset)
            for obj in objects:
                self._audit(request, ActionType.DELETE, obj)
            queryset.delete()


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("timestamp", "user", "username", "action", "resource_type", "resource_id", "ip_address")
    list_filter = ("action", "resource_type", "timestamp")
    search_fields = ("username", "resource_type", "resource_id", "ip_address")
    readonly_fields = (
        "id",
        "timestamp",
        "user",
        "username",
        "action",
        "resource_type",
        "resource_id",
        "ip_address",
        "details",
    )
    ordering = ("-timestamp",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
