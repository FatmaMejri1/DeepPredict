from datetime import datetime, timezone as dt_timezone
from django.db import transaction

from audit.models import ActionType
from audit.services import log_action
from alerts.services import process_prediction_alerts
from infrastructure.models import Resource, Status
from infrastructure.operational import operational_metrics, operational_resources
from ml_models.models import MLModelVersion, ModelType
from monitoring.models import Metric
from predictions import inference_client
from predictions.inference_client import (
    DriveModelCompatibilityError,
    InferenceError,
    NotEnoughHistory,
)
from predictions.models import Prediction

STATUS_BY_LEVEL = {
    "LOW": Status.HEALTHY,
    "MEDIUM": Status.WARNING,
    "HIGH": Status.HIGH_RISK,
    "CRITICAL": Status.HIGH_RISK,
}


def apply_risk_status(resource: Resource, risk_level: str):
    """Set the drive status from the failure-risk level, if it is recognized."""
    new_status = STATUS_BY_LEVEL.get(risk_level)
    if new_status is not None and resource.status != new_status:
        resource.status = new_status
        resource.save(update_fields=["status"])


def predict_resource(resource: Resource, as_of=None, actor=None, request=None, source=None):
    """
    Score a resource with the AI service.
    Returns (risk_prediction, anomaly_prediction) or None if skipped/no readings.
    """
    if not operational_resources(Resource.objects.filter(pk=resource.pk)).exists():
        raise InferenceError("Training/demo resources are excluded from operational prediction.")

    metrics = operational_metrics(
        Metric.objects.filter(resource=resource)
    ).order_by("timestamp")
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
    drive_model = (resource.attributes or {}).get("drive_model")
    if not isinstance(drive_model, str) or not drive_model.strip():
        raise DriveModelCompatibilityError(
            "Drive model metadata is missing; compatibility cannot be verified."
        )
    for m in metrics:
        row = {"date": m.timestamp.strftime("%Y-%m-%d")}
        if m.values:
            row.update({
                key: value
                for key, value in m.values.items()
                if key not in {"model", "drive_model"}
            })
        # Resource metadata is authoritative; telemetry values cannot supply
        # or replace either compatibility field.
        row["model"] = drive_model
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
        # Serialize persistence for this resource so concurrent successful
        # runs cannot race the active-alert lifecycle update.
        locked_resource = Resource.objects.select_for_update().get(pk=resource.pk)
        # Another run may have completed inference while this request waited
        # for the resource lock. Recheck freshness before persisting either
        # result so a duplicate run cannot increment alert occurrences.
        if Prediction.objects.filter(
            resource=locked_resource,
            model_version=risk_model,
            window_end__gte=last_metric.timestamp,
        ).exists():
            return None

        risk_pred = Prediction.objects.create(
            resource=locked_resource,
            model_version=risk_model,
            score=answer["risk_score"],
            risk_level=risk_level,
            horizon_days=answer.get("horizon_days", 7),
            window_start=window_start,
            window_end=window_end,
        )
        ano_pred = Prediction.objects.create(
            resource=locked_resource,
            model_version=ano_model,
            score=answer["anomaly_score"],
            is_anomalous=answer["is_anomalous"],
            window_start=window_start,
            window_end=window_end,
        )

        apply_risk_status(locked_resource, risk_level)
        process_prediction_alerts(locked_resource, risk_pred, ano_pred)

        audit_details = {
            "name": locked_resource.name,
            "identifier": locked_resource.identifier,
            "risk_score": answer["risk_score"],
            "risk_level": risk_level,
            "is_anomalous": answer["is_anomalous"],
            "status": locked_resource.status,
        }
        if source:
            audit_details["source"] = source
        log_action(
            action=ActionType.PREDICT_RUN,
            user=actor,
            request=request,
            resource_type="Resource",
            resource_id=str(locked_resource.pk),
            details=audit_details,
        )

    return risk_pred, ano_pred
