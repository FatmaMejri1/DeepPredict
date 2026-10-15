import uuid
from django.db import models
from django.db.models import Q


class ModelType(models.TextChoices):
    ANOMALY_DETECTION = "ANOMALY_DETECTION", "Anomaly detection"
    FAILURE_PREDICTION = "FAILURE_PREDICTION", "Failure prediction"


class MLModelVersion(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    model_type = models.CharField(max_length=30, choices=ModelType.choices)
    architecture = models.CharField(max_length=50)  # LSTM_AUTOENCODER, LSTM, GRU
    version = models.CharField(max_length=30)
    training_dataset = models.CharField(max_length=200)
    trained_at = models.DateTimeField()
    evaluation_metrics = models.JSONField(default=dict, blank=True)
    thresholds = models.JSONField(default=dict, blank=True)
    config = models.JSONField(default=dict, blank=True)  # preprocessing recipe
    artifact_uri = models.CharField(max_length=300, blank=True)
    is_active = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["name", "version"], name="unique_model_name_version"),
            # only one active model per model type
            models.UniqueConstraint(
                fields=["model_type"],
                condition=Q(is_active=True),
                name="one_active_model_per_type",
            ),
        ]

    def __str__(self):
        return f"{self.name} {self.version}"