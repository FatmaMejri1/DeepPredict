from datetime import datetime, timezone as dt_timezone
from django.db import transaction

from audit.models import ActionType
from audit.services import log_action
from infrastructure.models import Resource, Status
from ml_models.models import MLModelVersion, ModelType
from monitoring.models import Metric
from predictions import inference_client
from predictions.inference_client import InferenceError, NotEnoughHistory
from predictions.models import Prediction

STATUS_BY_LEVEL = {
    "LOW": Status.HEALTHY,
    "MEDIUM": Status.WARNING,
    "HIGH": Status.HIGH_RISK,
    "CRITICAL": Status.HIGH_RISK,
}


def predict_resource(resource: Resource, as_of=None):
    """
    Score a resource with the AI service.
    Returns (risk_prediction, anomaly_prediction) or None if skipped/no readings.
    """
    metrics = Metric.objects.filter(resource=resource).order_by("timestamp")
    if as_of:
        as_of_date = as_of.date() if hasattr(as_of, "date") else as_of
        metrics = metrics.filter(timestamp__date__lte=as_of_date)

    if not metrics.exists():
        return None

    last_metric = metrics.last()

    risk_model = MLModelVersion.objects.filter(
        model_type=ModelType.FAILURE_PREDICTION, is_active=True
    ).first()
    ano_model = MLModelVersion.objects.filter(
        model_type=ModelType.ANOMALY_DETECTION, is_active=True
    ).first()

    if not risk_model or not ano_model:
        raise InferenceError("No active model found for predictions.")

    # Check if already up to date
    if Prediction.objects.filter(
        resource=resource,
        model_version=risk_model,
        window_end__gte=last_metric.timestamp,
    ).exists():
        return None

    # Format readings
    readings = []
    for m in metrics:
        row = {"date": m.timestamp.strftime("%Y-%m-%d")}
        if m.values:
            row.update(m.values)
        readings.append(row)

    answer = inference_client.predict(readings)

    # Validate model version
    if answer.get("model_version") != risk_model.version:
        raise InferenceError(
            f"Model version mismatch: expected {risk_model.version}, got {answer.get('model_version')}"
        )

    # Parse window start/end
    window_start = datetime.fromisoformat(answer["window_start"])
    if window_start.tzinfo is None:
        window_start = window_start.replace(tzinfo=dt_timezone.utc)

    window_end = datetime.fromisoformat(answer["window_end"])
    if window_end.tzinfo is None:
        window_end = window_end.replace(tzinfo=dt_timezone.utc)

    risk_level = answer.get("risk_level")

    with transaction.atomic():
        risk_pred = Prediction.objects.create(
            resource=resource,
            model_version=risk_model,
            score=answer["risk_score"],
            risk_level=risk_level,
            horizon_days=answer.get("horizon_days", 7),
            window_start=window_start,
            window_end=window_end,
        )
        ano_pred = Prediction.objects.create(
            resource=resource,
            model_version=ano_model,
            score=answer["anomaly_score"],
            is_anomalous=answer["is_anomalous"],
            window_start=window_start,
            window_end=window_end,
        )

        if risk_level in STATUS_BY_LEVEL:
            new_status = STATUS_BY_LEVEL[risk_level]
            if resource.status != new_status:
                resource.status = new_status
                resource.save(update_fields=["status"])

        log_action(
            action=ActionType.PREDICT_RUN,
            resource_type="Resource",
            resource_id=str(resource.pk),
            details={
                "name": resource.name,
                "identifier": resource.identifier,
                "risk_score": answer["risk_score"],
                "risk_level": risk_level,
                "is_anomalous": answer["is_anomalous"],
                "status": resource.status,
            },
        )

    return risk_pred, ano_pred
