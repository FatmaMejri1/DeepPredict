"""Read-only, bounded query composition for a drive's unified event timeline."""

import heapq
from datetime import datetime, time, timezone as datetime_timezone

from django.db.models import CharField
from django.db.models.functions import Cast
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

from alerts.models import Alert
from audit.models import ActionType, AuditLog
from infrastructure.models import Resource
from monitoring.models import Metric
from predictions.models import Prediction


PAGE_SIZE = 20
MAX_PAGE_SIZE = 100
EVENT_TYPES = frozenset({
    "TELEMETRY_READING",
    "PREDICTION",
    "ALERT_OPENED",
    "ALERT_ACKNOWLEDGED",
    "ALERT_RESOLVED",
    "RESOURCE_AUDIT",
})


class TimelineInputError(ValueError):
    def __init__(self, field, detail):
        self.field = field
        self.detail = detail
        super().__init__(detail)


class TimelinePageNotFound(Exception):
    pass


def _parse_positive_int(params, name, default, maximum=None):
    raw = params.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise TimelineInputError(name, f"'{name}' must be a positive integer.")
    if value < 1 or (maximum is not None and value > maximum):
        if maximum is not None:
            detail = f"'{name}' must be between 1 and {maximum}."
        else:
            detail = f"'{name}' must be a positive integer."
        raise TimelineInputError(name, detail)
    return value


def _parse_bound(value, field, *, upper=False):
    if not value:
        return None
    parsed = parse_datetime(value)
    if parsed is None:
        parsed_day = parse_date(value)
        if parsed_day is None:
            raise TimelineInputError(field, f"'{field}' must be an ISO-8601 date or datetime.")
        parsed = datetime.combine(parsed_day, time.max if upper else time.min)
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
    return parsed


def _filters(params):
    event_type = params.get("type")
    if event_type is not None and event_type not in EVENT_TYPES:
        allowed = ", ".join(sorted(EVENT_TYPES))
        raise TimelineInputError("type", f"'type' must be one of: {allowed}.")

    start = _parse_bound(params.get("from"), "from")
    end = _parse_bound(params.get("to"), "to", upper=True)
    if start and end and start > end:
        raise TimelineInputError("from", "'from' must not be later than 'to'.")

    return {
        "type": event_type,
        "from": start,
        "to": end,
        "page": _parse_positive_int(params, "page", 1),
        "page_size": _parse_positive_int(params, "page_size", PAGE_SIZE, MAX_PAGE_SIZE),
    }


def _time_range(queryset, field, start, end):
    if start is not None:
        queryset = queryset.filter(**{f"{field}__gte": start})
    if end is not None:
        queryset = queryset.filter(**{f"{field}__lte": end})
    return queryset


def _event(event_type, event_id, occurred_at, resource, *, actor=None, data=None):
    return {
        "id": f"{event_type.lower()}:{event_id}",
        "event_type": event_type,
        "occurred_at": occurred_at.isoformat(),
        "resource": {
            "id": str(resource.pk),
            "name": resource.name,
            "identifier": resource.identifier,
        },
        "actor": actor or None,
        "data": data or {},
        "_occurred_at": occurred_at,
    }


def _event_streams(resource, filters):
    """Return (count, streaming iterator) pairs, one query pair per event type."""
    start, end = filters["from"], filters["to"]
    wanted = filters["type"]
    streams = []

    if wanted in (None, "TELEMETRY_READING"):
        qs = _time_range(Metric.objects.filter(resource_id=resource.pk), "timestamp", start, end)
        count = qs.count()
        rows = qs.annotate(_timeline_id=Cast("pk", output_field=CharField())).order_by(
            "-timestamp", "_timeline_id"
        ).values("pk", "timestamp", "source", "_timeline_id")
        events = (
            _event("TELEMETRY_READING", row["_timeline_id"], row["timestamp"], resource,
                   data={"source": row["source"]})
            for row in rows.iterator(chunk_size=200)
        )
        streams.append((count, events))

    if wanted in (None, "PREDICTION"):
        qs = _time_range(
            Prediction.objects.filter(resource_id=resource.pk).select_related("model_version"),
            "created_at", start, end,
        )
        count = qs.count()
        rows = qs.only(
            "pk", "resource_id", "model_version_id", "score", "is_anomalous", "risk_level",
            "horizon_days", "window_start", "window_end", "created_at",
            "model_version__name", "model_version__version", "model_version__model_type",
            "model_version__architecture",
        ).annotate(_timeline_id=Cast("pk", output_field=CharField())).order_by(
            "-created_at", "_timeline_id"
        )

        def prediction_events(rows=rows):
            for prediction in rows.iterator(chunk_size=200):
                model = prediction.model_version
                yield _event(
                    "PREDICTION", prediction.pk, prediction.created_at, resource,
                    actor=None,
                    data={
                        "prediction_type": model.model_type,
                        "score": prediction.score,
                        "risk_level": prediction.risk_level,
                        "is_anomalous": prediction.is_anomalous,
                        "horizon_days": prediction.horizon_days,
                        "window_start": prediction.window_start.isoformat(),
                        "window_end": prediction.window_end.isoformat(),
                        "model": {
                            "name": model.name,
                            "version": model.version,
                            "model_type": model.model_type,
                            "architecture": model.architecture,
                        },
                    },
                )
        streams.append((count, prediction_events()))

    if wanted in (None, "ALERT_OPENED"):
        qs = _time_range(Alert.objects.filter(resource_id=resource.pk), "first_seen_at", start, end)
        count = qs.count()
        rows = qs.only("pk", "alert_type", "severity", "first_seen_at").annotate(
            _timeline_id=Cast("pk", output_field=CharField())
        ).order_by("-first_seen_at", "_timeline_id")
        events = (
            _event("ALERT_OPENED", alert.pk, alert.first_seen_at, resource, data={
                "alert_id": str(alert.pk), "alert_type": alert.alert_type,
                "severity": alert.severity,
            })
            for alert in rows.iterator(chunk_size=200)
        )
        streams.append((count, events))

    if wanted in (None, "ALERT_ACKNOWLEDGED"):
        qs = _time_range(
            Alert.objects.filter(resource_id=resource.pk, acknowledged_at__isnull=False)
            .select_related("acknowledged_by"),
            "acknowledged_at", start, end,
        )
        count = qs.count()
        rows = qs.only(
            "pk", "alert_type", "severity", "acknowledged_at", "acknowledged_by_id",
            "acknowledged_by__username",
        ).annotate(_timeline_id=Cast("pk", output_field=CharField())).order_by(
            "-acknowledged_at", "_timeline_id"
        )
        events = (
            _event("ALERT_ACKNOWLEDGED", alert.pk, alert.acknowledged_at, resource,
                   actor=alert.acknowledged_by.username if alert.acknowledged_by_id else None,
                   data={"alert_id": str(alert.pk), "alert_type": alert.alert_type,
                         "severity": alert.severity})
            for alert in rows.iterator(chunk_size=200)
        )
        streams.append((count, events))

    if wanted in (None, "ALERT_RESOLVED"):
        qs = _time_range(
            Alert.objects.filter(resource_id=resource.pk, resolved_at__isnull=False)
            .select_related("resolved_by"),
            "resolved_at", start, end,
        )
        count = qs.count()
        rows = qs.only(
            "pk", "alert_type", "severity", "resolved_at", "resolved_by_id", "resolved_by__username",
            "resolution_source",
        ).annotate(_timeline_id=Cast("pk", output_field=CharField())).order_by(
            "-resolved_at", "_timeline_id"
        )
        events = (
            _event("ALERT_RESOLVED", alert.pk, alert.resolved_at, resource,
                   actor=alert.resolved_by.username if alert.resolved_by_id else None,
                   data={"alert_id": str(alert.pk), "alert_type": alert.alert_type,
                         "severity": alert.severity, "resolution_source": alert.resolution_source})
            for alert in rows.iterator(chunk_size=200)
        )
        streams.append((count, events))

    if wanted in (None, "RESOURCE_AUDIT"):
        qs = _time_range(AuditLog.objects.filter(
            resource_type="Resource",
            resource_id=str(resource.pk),
            action__in=(ActionType.CREATE, ActionType.UPDATE, ActionType.DELETE),
        ), "timestamp", start, end)
        count = qs.count()
        rows = qs.annotate(_timeline_id=Cast("pk", output_field=CharField())).order_by(
            "-timestamp", "_timeline_id"
        ).values("pk", "timestamp", "action", "username", "_timeline_id")
        descriptions = {
            ActionType.CREATE: "Resource created",
            ActionType.UPDATE: "Resource updated",
            ActionType.DELETE: "Resource deleted",
        }
        events = (
            _event("RESOURCE_AUDIT", row["_timeline_id"], row["timestamp"], resource,
                   actor=row["username"],
                   data={"action": row["action"], "description": descriptions[row["action"]]})
            for row in rows.iterator(chunk_size=200)
        )
        streams.append((count, events))

    return streams


def _sort_key(event):
    # Newest first. The event type and composite ID make equal timestamps stable.
    return (
        datetime.max.replace(tzinfo=datetime_timezone.utc)
        - event["_occurred_at"].astimezone(datetime_timezone.utc),
        event["event_type"],
        event["id"],
    )


def build_drive_timeline(resource, params):
    """Merge source iterators globally, then apply an accurate page slice.

    QuerySet.iterator keeps memory bounded by the database fetch chunk per
    source plus the requested page. Deep pages remain correct but require
    scanning and skipping preceding events; cursor pagination would require a
    separate API contract decision if deep-page latency becomes significant.
    """
    filters = _filters(params)
    page, page_size = filters["page"], filters["page_size"]
    offset = (page - 1) * page_size
    streams = _event_streams(resource, filters)
    count = sum(stream_count for stream_count, _ in streams)

    if page > 1 and offset >= count:
        raise TimelinePageNotFound

    ordered_events = heapq.merge(
        *(stream_events for _, stream_events in streams), key=_sort_key
    )
    page_events = []
    try:
        for event_index, event in enumerate(ordered_events):
            if event_index < offset:
                continue
            if len(page_events) >= page_size:
                break
            event.pop("_occurred_at", None)
            page_events.append(event)
    finally:
        ordered_events.close()
        for _, stream_events in streams:
            close = getattr(stream_events, "close", None)
            if close:
                close()

    return {"count": count, "results": page_events, "page": page, "page_size": page_size}
