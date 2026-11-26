"""Query helpers that keep model-training samples out of operational views."""

from django.db.models import Exists, OuterRef, Q

from infrastructure.models import Resource
from monitoring.models import Metric


TRAINING_METRIC_SOURCES = ("backblaze", "backblaze_replay")


def training_metrics(queryset=None):
    """Return telemetry explicitly marked as Backblaze training/replay data."""
    queryset = queryset if queryset is not None else Metric.objects.all()
    training_source = Q()
    for source in TRAINING_METRIC_SOURCES:
        training_source |= Q(source__iexact=source)
    return queryset.filter(training_source)


def operational_metrics(queryset=None):
    """Exclude telemetry whose persisted source identifies Backblaze data."""
    queryset = queryset if queryset is not None else Metric.objects.all()
    training_source = Q()
    for source in TRAINING_METRIC_SOURCES:
        training_source |= Q(source__iexact=source)
    return queryset.exclude(training_source)


def operational_resources(queryset=None):
    """Exclude resources marked demo or linked to Backblaze telemetry.

    The metric-source check also catches rows inserted by the historical loader
    when it reused an existing Resource and therefore did not set ``demo``.
    """
    queryset = queryset if queryset is not None else Resource.objects.all()
    backblaze_rows = training_metrics(Metric.objects.filter(resource_id=OuterRef("pk")))
    return (
        queryset.annotate(_has_training_telemetry=Exists(backblaze_rows))
        .filter(_has_training_telemetry=False)
        .filter(Q(attributes__demo__isnull=True) | Q(attributes__demo=False))
    )
