import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


class AlertType(models.TextChoices):
    FAILURE_RISK = "FAILURE_RISK", "Failure risk"
    ANOMALY = "ANOMALY", "Anomaly"


class AlertStatus(models.TextChoices):
    OPEN = "OPEN", "Open"
    ACKNOWLEDGED = "ACKNOWLEDGED", "Acknowledged"
    RESOLVED = "RESOLVED", "Resolved"


class AlertSeverity(models.TextChoices):
    HIGH = "HIGH", "High"
    CRITICAL = "CRITICAL", "Critical"


class Alert(models.Model):
    """One durable row per alert episode; each resolved recurrence gets a new row."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    resource = models.ForeignKey(
        "infrastructure.Resource", on_delete=models.PROTECT, related_name="alerts"
    )
    alert_type = models.CharField(max_length=20, choices=AlertType.choices)
    severity = models.CharField(max_length=10, choices=AlertSeverity.choices)
    status = models.CharField(max_length=20, choices=AlertStatus.choices, default=AlertStatus.OPEN)
    first_seen_at = models.DateTimeField()
    last_seen_at = models.DateTimeField()
    occurrence_count = models.PositiveIntegerField(default=1)
    consecutive_clear_count = models.PositiveSmallIntegerField(default=0)
    latest_prediction = models.ForeignKey(
        "predictions.Prediction",
        null=True,
        blank=True,
        # Existing Admin permits prediction deletion. Preserve the alert
        # episode if that path is used, while retaining its link otherwise.
        on_delete=models.SET_NULL,
        related_name="latest_for_alerts",
    )
    acknowledged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="acknowledged_alerts",
    )
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="resolved_alerts",
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_source = models.CharField(
        max_length=10,
        choices=(("AUTO", "Automatic"), ("USER", "User")),
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-last_seen_at", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["resource", "alert_type"],
                condition=Q(status__in=[AlertStatus.OPEN, AlertStatus.ACKNOWLEDGED]),
                name="one_active_alert_per_resource_type",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        status__in=(AlertStatus.OPEN, AlertStatus.ACKNOWLEDGED),
                        consecutive_clear_count__lte=1,
                    )
                    | Q(status=AlertStatus.RESOLVED, consecutive_clear_count__lte=2)
                ),
                name="alert_clear_count_at_most_two",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        status=AlertStatus.OPEN,
                        acknowledged_at__isnull=True,
                        acknowledged_by__isnull=True,
                        resolved_at__isnull=True,
                        resolved_by__isnull=True,
                        resolution_source="",
                    )
                    | Q(
                        status=AlertStatus.ACKNOWLEDGED,
                        acknowledged_at__isnull=False,
                        resolved_at__isnull=True,
                        resolved_by__isnull=True,
                        resolution_source="",
                    )
                    | Q(
                        status=AlertStatus.RESOLVED,
                        resolved_at__isnull=False,
                        resolution_source="AUTO",
                        consecutive_clear_count=2,
                    )
                    | Q(
                        status=AlertStatus.RESOLVED,
                        resolved_at__isnull=False,
                        resolution_source="USER",
                    )
                ),
                name="alert_lifecycle_fields_consistent",
            ),
            models.CheckConstraint(
                condition=Q(acknowledged_by__isnull=True) | Q(acknowledged_at__isnull=False),
                name="alert_ack_actor_requires_time",
            ),
            models.CheckConstraint(
                condition=Q(resolved_by__isnull=True) | Q(resolution_source="USER"),
                name="alert_resolver_requires_user_source",
            ),
        ]
        indexes = [
            models.Index(fields=["status", "-last_seen_at"], name="alerts_status_seen_idx"),
            models.Index(fields=["resource", "-created_at"], name="alerts_resource_created_idx"),
            models.Index(fields=["alert_type", "status", "severity"], name="alerts_type_status_sev_idx"),
        ]

    def __str__(self):
        return f"{self.get_alert_type_display()} {self.severity} for {self.resource_id} ({self.status})"

    def clean(self):
        errors = {}
        if self.consecutive_clear_count < 0 or self.consecutive_clear_count > 2:
            errors["consecutive_clear_count"] = "The consecutive clear count must be between zero and two."
        if self.status == AlertStatus.OPEN:
            if any((self.acknowledged_at, self.acknowledged_by_id, self.resolved_at,
                    self.resolved_by_id, self.resolution_source)):
                errors["status"] = "An open alert cannot have acknowledgement or resolution details."
            if self.consecutive_clear_count >= 2:
                errors["consecutive_clear_count"] = "An alert with two clear predictions must be resolved."
        elif self.status == AlertStatus.ACKNOWLEDGED:
            if not self.acknowledged_at:
                errors["acknowledged_at"] = "An acknowledged alert must have an acknowledgement timestamp."
            if any((self.resolved_at, self.resolved_by_id, self.resolution_source)):
                errors["status"] = "An acknowledged alert cannot have resolution details."
            if self.consecutive_clear_count >= 2:
                errors["consecutive_clear_count"] = "An alert with two clear predictions must be resolved."
        elif self.status == AlertStatus.RESOLVED:
            if not self.resolved_at:
                errors["resolved_at"] = "A resolved alert must have a resolution timestamp."
            if self.resolution_source not in ("AUTO", "USER"):
                errors["resolution_source"] = "A resolved alert must have a valid resolution source."
            if self.resolution_source == "AUTO" and self.consecutive_clear_count != 2:
                errors["consecutive_clear_count"] = "Automatic resolution requires two clear predictions."
            if self.resolved_by_id and self.resolution_source != "USER":
                errors["resolved_by"] = "Only a user-resolved alert can have a resolving user."
        else:
            errors["status"] = "Unknown alert lifecycle status."

        if self.acknowledged_by_id and not self.acknowledged_at:
            errors["acknowledged_by"] = "An acknowledging user requires an acknowledgement timestamp."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        # Match Prediction's validation pattern; database constraints also
        # enforce these rules for bulk updates and concurrent writes.
        self.clean()
        return super().save(*args, **kwargs)
