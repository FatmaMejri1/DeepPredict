from django.db import models


class Metric(models.Model):
    """One row per resource per timestamp. `values` holds all features of that moment."""

    resource = models.ForeignKey(
        "infrastructure.Resource", on_delete=models.CASCADE, related_name="metrics"
    )
    timestamp = models.DateTimeField()
    values = models.JSONField(default=dict)
    source = models.CharField(max_length=100, blank=True)

    class Meta:
        constraints = [
            # also creates the index on (resource, timestamp)
            models.UniqueConstraint(
                fields=["resource", "timestamp"], name="unique_metric_resource_timestamp"
            )
        ]

    def __str__(self):
        return f"{self.resource_id} @ {self.timestamp:%Y-%m-%d %H:%M}"