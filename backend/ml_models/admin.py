from django.contrib import admin
from audit.admin import AuditLoggedModelAdmin
from .models import MLModelVersion


@admin.register(MLModelVersion)
class MLModelVersionAdmin(AuditLoggedModelAdmin):
    audit_configuration_changes = True
    list_display = ("name", "version", "model_type", "is_active", "trained_at")
    list_filter = ("model_type", "is_active")
