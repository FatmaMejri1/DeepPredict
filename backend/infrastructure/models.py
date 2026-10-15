import uuid
from django.conf import settings
from django.db import models


class ResourceType(models.TextChoices):
    SERVER = "SERVER", "Server"
    DISK = "DISK", "Disk"
    WORKLOAD = "WORKLOAD", "Workload"
    CLOUD = "CLOUD", "Cloud resource"


class Status(models.TextChoices):
    HEALTHY = "HEALTHY", "Healthy"
    WARNING = "WARNING", "Warning"
    HIGH_RISK = "HIGH_RISK", "High risk"


class Resource(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=150)
    resource_type = models.CharField(max_length=20, choices=ResourceType.choices)
    identifier = models.CharField(max_length=150, unique=True)
    attributes = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.HEALTHY)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_resources",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} [{self.resource_type}]"