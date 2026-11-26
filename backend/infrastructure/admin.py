from django.contrib import admin
from audit.admin import AuditLoggedModelAdmin
from infrastructure.operational import operational_resources
from .models import Resource


@admin.register(Resource)
class ResourceAdmin(AuditLoggedModelAdmin):
    list_display = ("name", "identifier", "resource_type", "status", "is_active", "created_at")
    list_filter = ("resource_type", "status", "is_active")
    search_fields = ("name", "identifier")
    readonly_fields = ("created_at", "updated_at")

    def get_queryset(self, request):
        return operational_resources(super().get_queryset(request))

    def save_model(self, request, obj, form, change):
        if not change and not obj.created_by:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
