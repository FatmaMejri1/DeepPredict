from django.core.exceptions import ValidationError
from django.db import models

from ml_models.models import ModelType


class RiskLevel(models.TextChoices):
    # LOW = HEALTHY, MEDIUM = WARNING, HIGH = HIGH_RISK
    LOW = "LOW", "Low"
    MEDIUM = "MEDIUM", "Medium"
    HIGH = "HIGH", "High"


class Prediction(models.Model):
    resource = models.ForeignKey(
        "infrastructure.Resource", on_delete=models.CASCADE, related_name="predictions"
    )
    model_version = models.ForeignKey(
        "ml_models.MLModelVersion", on_delete=models.PROTECT, related_name="predictions"
    )
    score = models.FloatField()
    is_anomalous = models.BooleanField(null=True, blank=True)  # anomaly model only
    horizon_days = models.PositiveIntegerField(null=True, blank=True)  # risk model only
    risk_level = models.CharField(
        max_length=10, choices=RiskLevel.choices, null=True, blank=True
    )  # risk model only
    window_start = models.DateTimeField()
    window_end = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["resource", "-created_at"])]

    def clean(self):
        if self.window_end and self.window_start and self.window_end < self.window_start:
            raise ValidationError("window_end must not be before window_start.")
        if not self.model_version_id:
            return
        if self.model_version.model_type == ModelType.ANOMALY_DETECTION:
            if self.is_anomalous is None:
                raise ValidationError("is_anomalous is required for an anomaly prediction.")
            if self.horizon_days is not None or self.risk_level:
                raise ValidationError("horizon_days and risk_level must be empty for an anomaly.")
        else:
            if self.horizon_days is None or not self.risk_level:
                raise ValidationError("horizon_days and risk_level are required for a failure risk.")
            if self.is_anomalous is not None:
                raise ValidationError("is_anomalous must be empty for a failure risk.")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.model_version} score={self.score:.3f} on {self.resource_id}"