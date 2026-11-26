from django.db import transaction

from .models import Alert, AlertSeverity, AlertStatus, AlertType


# Fixed operational classification: do not infer anomaly severity from the
# model score because no score-to-severity mapping has been validated.
ANOMALY_ALERT_SEVERITY = AlertSeverity.HIGH
RISK_ALERT_LEVELS = {"HIGH": AlertSeverity.HIGH, "CRITICAL": AlertSeverity.CRITICAL}
CLEAR_PREDICTIONS_REQUIRED = 2


def _apply_prediction(alert_type, prediction, resource, qualifying, severity=None):
    active = Alert.objects.filter(
        resource=resource,
        alert_type=alert_type,
        status__in=(AlertStatus.OPEN, AlertStatus.ACKNOWLEDGED),
    ).select_for_update().first()

    if qualifying:
        if active is None:
            Alert.objects.create(
                resource=resource,
                alert_type=alert_type,
                severity=severity,
                first_seen_at=prediction.created_at,
                last_seen_at=prediction.created_at,
                latest_prediction=prediction,
            )
            return

        active.last_seen_at = prediction.created_at
        active.occurrence_count += 1
        active.consecutive_clear_count = 0
        active.latest_prediction = prediction
        active.severity = severity
        active.save(update_fields=[
            "last_seen_at", "occurrence_count", "consecutive_clear_count",
            "latest_prediction", "severity", "updated_at",
        ])
        return

    if active is None:
        return

    active.consecutive_clear_count += 1
    if active.consecutive_clear_count >= CLEAR_PREDICTIONS_REQUIRED:
        active.status = AlertStatus.RESOLVED
        active.resolved_at = prediction.created_at
        active.resolution_source = "AUTO"
    active.save(update_fields=[
        "consecutive_clear_count", "status", "resolved_at", "resolution_source", "updated_at",
    ])


@transaction.atomic
def process_prediction_alerts(resource, risk_prediction, anomaly_prediction):
    """Apply a successfully persisted prediction pair to alert state.

    The prediction caller invokes this within its atomic block. Locking the
    resource serializes lifecycle updates; the partial unique constraint is
    the database-level protection against duplicate active episodes.
    """
    # All alert lifecycle writers lock the resource first, then the active alert.
    # This makes manual actions and predictions serialize on the same row and
    # prevents a prediction from updating an episode after manual resolution.
    type(resource).objects.select_for_update().get(pk=resource.pk)

    risk_severity = RISK_ALERT_LEVELS.get(risk_prediction.risk_level)
    _apply_prediction(
        AlertType.FAILURE_RISK, risk_prediction, resource,
        qualifying=risk_severity is not None, severity=risk_severity,
    )
    _apply_prediction(
        AlertType.ANOMALY, anomaly_prediction, resource,
        qualifying=anomaly_prediction.is_anomalous is True,
        severity=ANOMALY_ALERT_SEVERITY,
    )
