from django.contrib import admin
from audit.admin import AuditLoggedModelAdmin
from .models import Prediction


@admin.register(Prediction)
class PredictionAdmin(AuditLoggedModelAdmin):
    list_display = ("resource", "model_version", "score", "risk_level", "created_at")
    list_filter = ("risk_level", "model_version__model_type")
