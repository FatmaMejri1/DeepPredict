"""Read-only queries behind the dashboard pages (views stay thin)."""
from django.db.models import Count, F, Max, OuterRef, Subquery

from infrastructure.models import Resource, ResourceType
from ml_models.models import MLModelVersion, ModelType
from monitoring.models import Metric
from predictions.models import Prediction

# the SMART counters drawn on the detail page
SMART_SERIES = [
    ("smart_5_raw", "Reallocated sectors (5)"),
    ("smart_187_raw", "Uncorrectable errors (187)"),
    ("smart_197_raw", "Pending sectors (197)"),
]


def disks_with_latest():
    """Active disks, each annotated with its latest risk level/score and anomaly flag."""
    risk = Prediction.objects.filter(
        resource=OuterRef("pk"), model_version__model_type=ModelType.FAILURE_PREDICTION
    ).order_by("-window_end")
    anomaly = Prediction.objects.filter(
        resource=OuterRef("pk"), model_version__model_type=ModelType.ANOMALY_DETECTION
    ).order_by("-window_end")
    last_reading = Metric.objects.filter(resource=OuterRef("pk")).order_by("-timestamp")
    return Resource.objects.filter(resource_type=ResourceType.DISK, is_active=True).annotate(
        risk_level=Subquery(risk.values("risk_level")[:1]),
        risk_score=Subquery(risk.values("score")[:1]),
        scored_until=Subquery(risk.values("window_end")[:1]),
        is_anomalous=Subquery(anomaly.values("is_anomalous")[:1]),
        last_reading=Subquery(last_reading.values("timestamp")[:1]),
    )


def summary_data():
    disks = Resource.objects.filter(resource_type=ResourceType.DISK, is_active=True)
    by_status = {row["status"]: row["n"] for row in disks.values("status").annotate(n=Count("id"))}
    annotated = disks_with_latest()
    return {
        "total": sum(by_status.values()),
        "healthy": by_status.get("HEALTHY", 0),
        "warning": by_status.get("WARNING", 0),
        "high_risk": by_status.get("HIGH_RISK", 0),
        "anomalous": annotated.filter(is_anomalous=True).count(),
        "not_scored": annotated.filter(risk_level__isnull=True).count(),
        "top": annotated.filter(risk_score__isnull=False).order_by(F("risk_score").desc())[:10],
        "data_until": Metric.objects.aggregate(m=Max("timestamp"))["m"],
    }


def active_risk_thresholds():
    version = MLModelVersion.objects.filter(
        model_type=ModelType.FAILURE_PREDICTION, is_active=True).first()
    return version.thresholds if version else {}


def chart_data(resource, days=90):
    """Everything the two charts of the detail page need, as plain lists."""
    rows = list(Metric.objects.filter(resource=resource).order_by("-timestamp")[:days])[::-1]
    smart = {
        "labels": [m.timestamp.strftime("%Y-%m-%d") for m in rows],
        "series": [{"label": label, "values": [m.values.get(key) for m in rows]}
                   for key, label in SMART_SERIES],
    }
    preds = list(Prediction.objects.filter(
        resource=resource, model_version__model_type=ModelType.FAILURE_PREDICTION
    ).order_by("-window_end")[:120])[::-1]
    risk = {
        "labels": [p.window_end.strftime("%Y-%m-%d") for p in preds],
        "scores": [p.score for p in preds],
    }
    return {"smart": smart, "risk": risk, "thresholds": active_risk_thresholds()}


def model_cards():
    """One dict per model version, with its evaluation ready to show as table rows."""
    cards = []
    for version in MLModelVersion.objects.order_by("model_type", "-is_active", "-trained_at"):
        results = (version.evaluation_metrics or {}).get("results", {})
        rows = []
        if version.model_type == ModelType.FAILURE_PREDICTION:
            for level in ("medium", "high", "critical"):
                if level in results:
                    rows.append({
                        "label": level.upper(),
                        "threshold": version.thresholds.get(level),
                        "healthy": results[level]["healthy_drives_flagged"] * 100,
                        "failed": results[level]["failed_drives_detected"] * 100,
                    })
        elif results:
            rows.append({
                "label": "ANOMALOUS",
                "threshold": version.thresholds.get("anomaly"),
                "healthy": results.get("healthy_drives_flagged", 0) * 100,
                "failed": results.get("failed_drives_detected", 0) * 100,
            })
        cards.append({"obj": version, "rows": rows,
                      "protocol": (version.evaluation_metrics or {}).get("protocol", "")})
    return cards
