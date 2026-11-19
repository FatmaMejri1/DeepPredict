from django.contrib import admin
from audit.models import ActionType
from audit.services import log_action
from .models import Resource


@admin.register(Resource)
class ResourceAdmin(admin.ModelAdmin):
    list_display = ("name", "identifier", "resource_type", "status", "is_active", "created_at")
    list_filter = ("resource_type", "status", "is_active")
    search_fields = ("name", "identifier")
    readonly_fields = ("created_at", "updated_at")

    def save_model(self, request, obj, form, change):
        is_new = not change
        if is_new and not obj.created_by:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
        log_action(
            action=ActionType.CREATE if is_new else ActionType.UPDATE,
            user=request.user,
            resource_type="Resource",
            resource_id=str(obj.pk),
            details={
                "name": obj.name,
                "identifier": obj.identifier,
                "status": obj.status,
                "action": "create" if is_new else "update",
            },
            request=request,
        )

    def delete_model(self, request, obj):
        res_id = str(obj.pk)
        name = obj.name
        super().delete_model(request, obj)
        log_action(
            action=ActionType.DELETE,
            user=request.user,
            resource_type="Resource",
            resource_id=res_id,
            details={"name": name, "action": "delete"},
            request=request,
        )
