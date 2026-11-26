from django.contrib import admin
from audit.admin import AuditLoggedModelAdmin
from infrastructure.operational import operational_metrics, operational_resources
from .models import Metric


@admin.register(Metric)
class MetricAdmin(AuditLoggedModelAdmin):
    list_display = ("resource", "timestamp", "source")
    list_filter = ("source",)

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        operational_resource_ids = operational_resources().values("pk")
        return operational_metrics(queryset).filter(resource_id__in=operational_resource_ids)
