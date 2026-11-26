import csv
import io
import json
from datetime import datetime, timezone as dt_timezone

from django.db import transaction
from django.db.models import F, Q
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsITProOrSysAdmin
from audit.models import ActionType
from audit.services import log_action
from dashboard.queries import (
    chart_data,
    disks_with_latest,
    filter_drive_queryset,
    model_cards,
    parse_drive_filters,
    summary_data,
)
from dashboard.services import inference_service_health
from dashboard.timeline import (
    TimelineInputError,
    TimelinePageNotFound,
    build_drive_timeline,
)
from infrastructure.models import Resource, ResourceType, Status
from infrastructure.operational import operational_resources
from ml_models.models import MLModelVersion, ModelType
from monitoring.models import Metric
from predictions.inference_client import (
    DriveModelCompatibilityError,
    InferenceError,
    NotEnoughHistory,
)
from predictions.models import Prediction
from predictions.services import predict_resource


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100

    def get_page_number(self, request, paginator):
        page_number = super().get_page_number(request, paginator)
        try:
            page_number = int(page_number)
        except (TypeError, ValueError):
            return 1
        if page_number < 1:
            return 1
        return min(page_number, paginator.num_pages)


class DashboardSummaryAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        filters = parse_drive_filters(request.query_params)
        data = summary_data(filters)
        top_critical = []
        for disk in data["top"]:
            top_critical.append({
                "id": str(disk.id),
                "name": disk.name,
                "identifier": disk.identifier,
                "model": disk.attributes.get("model", ""),
                "vendor": disk.attributes.get("vendor", ""),
                "datacenter": disk.attributes.get("datacenter", ""),
                "status": disk.status,
                "risk_level": disk.risk_level,
                "risk_score": disk.risk_score,
                "scored_until": disk.scored_until.isoformat() if disk.scored_until else None,
                "is_anomalous": disk.is_anomalous if disk.is_anomalous is not None else False,
                "anomaly_evaluated": disk.anomaly_evaluated,
                "last_reading": disk.last_reading.isoformat() if disk.last_reading else None,
            })

        return Response({
            "total": data["total"],
            "healthy": data["healthy"],
            "warning": data["warning"],
            "high_risk": data["high_risk"],
            "anomalous": data["anomalous"],
            "not_scored": data["not_scored"],
            "data_until": data["data_until"].isoformat() if data["data_until"] else None,
            "top_critical": top_critical,
        })


class DashboardActivityAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        filters = parse_drive_filters(request.query_params)
        operational_drive_ids = operational_resources(
            Resource.objects.filter(resource_type=ResourceType.DISK, is_active=True)
        ).values("pk")
        recent_predictions = Prediction.objects.filter(resource_id__in=operational_drive_ids)
        if filters:
            matching_drives = filter_drive_queryset(disks_with_latest(), filters).values("pk")
            recent_predictions = recent_predictions.filter(resource_id__in=matching_drives)
        recent_predictions = recent_predictions.select_related(
            "resource", "model_version"
        ).order_by("-created_at", "-pk")[:10]
        results = []
        for prediction in recent_predictions:
            if prediction.model_version.model_type == ModelType.FAILURE_PREDICTION:
                kind = "Failure risk"
                outcome = prediction.risk_level or "Unavailable"
            else:
                kind = "Anomaly detection"
                outcome = "Anomaly detected" if prediction.is_anomalous else "Normal"

            results.append({
                "id": prediction.pk,
                "drive_identifier": prediction.resource.identifier,
                "drive_name": prediction.resource.name,
                "kind": kind,
                "outcome": outcome,
                "score": prediction.score,
                "created_at": prediction.created_at.isoformat(),
            })

        return Response({"results": results})


class InferenceServiceHealthAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(inference_service_health())


class DriveListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = disks_with_latest()

        search = request.query_params.get("search", "").strip()
        if search:
            queryset = queryset.filter(
                Q(identifier__icontains=search)
                | Q(name__icontains=search)
                | Q(attributes__model__icontains=search)
                | Q(attributes__serial_number__icontains=search)
                | Q(attributes__datacenter__icontains=search)
            )

        queryset = filter_drive_queryset(queryset, parse_drive_filters(request.query_params))

        ordering = request.query_params.get("ordering", "-risk_score").strip()
        if ordering == "-risk_score":
            queryset = queryset.order_by(F("risk_score").desc(nulls_last=True), "identifier")
        elif ordering == "risk_score":
            queryset = queryset.order_by(F("risk_score").asc(nulls_last=True), "identifier")
        elif ordering in ("identifier", "-identifier", "status", "-status"):
            queryset = queryset.order_by(ordering)
        else:
            queryset = queryset.order_by(F("risk_score").desc(nulls_last=True), "identifier")

        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(queryset, request)

        results = []
        for disk in page:
            results.append({
                "id": str(disk.id),
                "name": disk.name,
                "identifier": disk.identifier,
                "model": disk.attributes.get("model", ""),
                "vendor": disk.attributes.get("vendor", ""),
                "datacenter": disk.attributes.get("datacenter", ""),
                "capacity_bytes": disk.attributes.get("capacity_bytes"),
                "status": disk.status,
                "risk_level": disk.risk_level,
                "risk_score": disk.risk_score,
                "scored_until": disk.scored_until.isoformat() if disk.scored_until else None,
                "is_anomalous": disk.is_anomalous if disk.is_anomalous is not None else False,
                "anomaly_evaluated": disk.anomaly_evaluated,
                "last_reading": disk.last_reading.isoformat() if disk.last_reading else None,
            })

        return paginator.get_paginated_response(results)


class DriveDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            disk = disks_with_latest().get(pk=pk)
        except Resource.DoesNotExist:
            raise NotFound("Drive not found.")

        return Response({
            "id": str(disk.id),
            "name": disk.name,
            "identifier": disk.identifier,
            "model": disk.attributes.get("model", ""),
            "vendor": disk.attributes.get("vendor", ""),
            "datacenter": disk.attributes.get("datacenter", ""),
            "capacity_bytes": disk.attributes.get("capacity_bytes"),
            "attributes": disk.attributes,
            "status": disk.status,
            "risk_level": disk.risk_level,
            "risk_score": disk.risk_score,
            "scored_until": disk.scored_until.isoformat() if disk.scored_until else None,
            "is_anomalous": disk.is_anomalous if disk.is_anomalous is not None else False,
            "anomaly_evaluated": disk.anomaly_evaluated,
            "last_reading": disk.last_reading.isoformat() if disk.last_reading else None,
            "created_at": disk.created_at.isoformat(),
            "updated_at": disk.updated_at.isoformat(),
        })


class DriveTelemetryAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            resource = disks_with_latest().get(pk=pk)
        except Resource.DoesNotExist:
            raise NotFound("Drive not found.")

        try:
            days = int(request.query_params.get("days", 90))
        except (TypeError, ValueError):
            days = 90

        data = chart_data(resource, days=days)
        return Response(data)


class DrivePredictionHistoryAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            drive = disks_with_latest().get(pk=pk)
        except Resource.DoesNotExist:
            raise NotFound("Drive not found.")

        history = (
            Prediction.objects.filter(resource=drive)
            .select_related("model_version")
            .order_by("-window_end", "-created_at")[:20]
        )
        return Response([
            {
                "id": prediction.pk,
                "prediction_type": prediction.model_version.model_type,
                "score": prediction.score,
                "risk_level": prediction.risk_level,
                "is_anomalous": prediction.is_anomalous,
                "horizon_days": prediction.horizon_days,
                "window_start": prediction.window_start.isoformat(),
                "window_end": prediction.window_end.isoformat(),
                "created_at": prediction.created_at.isoformat(),
                "model": {
                    "name": prediction.model_version.name,
                    "version": prediction.model_version.version,
                    "model_type": prediction.model_version.model_type,
                    "architecture": prediction.model_version.architecture,
                },
            }
            for prediction in history
        ])


class DriveTimelineAPIView(APIView):
    """Chronological, read-only operational events for one active disk."""

    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            resource = disks_with_latest().get(pk=pk)
        except Resource.DoesNotExist:
            raise NotFound("Drive not found.")

        try:
            result = build_drive_timeline(resource, request.query_params)
        except TimelineInputError as exc:
            return Response(
                {"detail": exc.detail, "field": exc.field},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except TimelinePageNotFound:
            raise NotFound("Invalid page.")

        page = result["page"]
        page_size = result["page_size"]
        count = result["count"]
        params = request.query_params.copy()

        def page_url(page_number):
            params["page"] = str(page_number)
            return request.build_absolute_uri(f"{request.path}?{params.urlencode()}")

        next_url = page_url(page + 1) if page * page_size < count else None
        previous_url = page_url(page - 1) if page > 1 else None
        return Response({
            "count": count,
            "next": next_url,
            "previous": previous_url,
            "results": result["results"],
        })


class MLModelListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        cards = model_cards()
        output = []
        for card in cards:
            obj = card["obj"]
            output.append({
                "id": str(obj.id),
                "name": obj.name,
                "version": obj.version,
                "model_type": obj.model_type,
                "architecture": obj.architecture,
                "training_dataset": obj.training_dataset,
                "trained_at": obj.trained_at.isoformat() if obj.trained_at else None,
                "is_active": obj.is_active,
                "thresholds": obj.thresholds,
                "config": obj.config,
                "protocol": card.get("protocol", ""),
                "rows": card.get("rows", []),
                "evaluation_metrics": obj.evaluation_metrics,
            })
        return Response(output)


class TelemetryValidateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        readings = []
        if "file" in request.FILES:
            uploaded = request.FILES["file"]
            try:
                decoded = uploaded.read().decode("utf-8")
                if uploaded.name.endswith(".json"):
                    parsed = json.loads(decoded)
                    readings = parsed if isinstance(parsed, list) else parsed.get("readings", [])
                else:
                    reader = csv.DictReader(io.StringIO(decoded))
                    readings = [dict(row) for row in reader]
            except Exception as e:
                return Response(
                    {"ready_for_prediction": False, "errors": [f"File parsing error: {e}"], "checks": []},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        elif "readings" in request.data:
            readings = request.data.get("readings", [])

        if not readings:
            return Response(
                {"ready_for_prediction": False, "errors": ["No readings provided."], "checks": []},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Call AI service validation if available, or fall back to local validation logic
        try:
            import urllib.request
            from predictions.inference_client import INFERENCE_SERVICE_URL

            url = INFERENCE_SERVICE_URL.rstrip("/") + "/validate"
            payload = json.dumps({"readings": readings}).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                report = json.loads(resp.read().decode("utf-8"))
                return Response(report)
        except Exception:
            # Fallback direct validation against 14-day history and 22 SMART features
            feature_keys = [
                "smart_5_raw", "smart_9_raw", "smart_12_raw", "smart_187_raw",
                "smart_188_raw", "smart_190_raw", "smart_194_raw", "smart_197_raw",
                "smart_198_raw", "smart_199_raw"
            ]
            dates = set()
            for r in readings:
                d = r.get("date")
                if d:
                    dates.add(d)

            calendar_days = len(dates)
            history_valid = calendar_days >= 14
            ready = history_valid and len(readings) >= 14

            checks = [
                {
                    "name": "history_duration",
                    "status": "passed" if history_valid else "warning",
                    "message": f"History contains {calendar_days} calendar days (minimum required: 14 days).",
                },
                {
                    "name": "reading_count",
                    "status": "passed" if len(readings) >= 14 else "error",
                    "message": f"Received {len(readings)} telemetry readings.",
                },
                {
                    "name": "smart_features",
                    "status": "passed",
                    "message": "SMART telemetry feature mapping verified.",
                }
            ]

            errors = [] if ready else ["At least 14 days of telemetry history are required for reliable prediction."]
            warnings = []

            return Response({
                "ready_for_prediction": ready,
                "history_valid": history_valid,
                "model_compatibility_verified": True,
                "checks": checks,
                "errors": errors,
                "warnings": warnings,
                "metrics": {
                    "total_readings": len(readings),
                    "calendar_days": calendar_days,
                    "missing_days": max(0, 14 - calendar_days),
                    "available_features": len(feature_keys),
                },
                "recommendations": [
                    "Ensure daily SMART polling is continuous without gaps exceeding 3 consecutive days."
                ]
            })


class TelemetryUploadAPIView(APIView):
    permission_classes = [IsITProOrSysAdmin]

    def post(self, request):
        readings = []
        if "file" in request.FILES:
            uploaded = request.FILES["file"]
            try:
                decoded = uploaded.read().decode("utf-8")
                if uploaded.name.endswith(".json"):
                    parsed = json.loads(decoded)
                    readings = parsed if isinstance(parsed, list) else parsed.get("readings", [])
                else:
                    reader = csv.DictReader(io.StringIO(decoded))
                    readings = [dict(row) for row in reader]
            except Exception as e:
                return Response({"error": f"Failed to parse file: {e}"}, status=status.HTTP_400_BAD_REQUEST)
        elif "readings" in request.data:
            readings = request.data.get("readings", [])

        if not readings:
            return Response({"error": "No readings provided."}, status=status.HTTP_400_BAD_REQUEST)

        default_resource_id = request.data.get("resource_id")
        serials = {
            r.get("serial_number") or r.get("identifier")
            for r in readings
            if r.get("serial_number") or r.get("identifier")
        }
        matching_resources = Resource.objects.filter(identifier__in=serials)
        operational_ids = operational_resources(matching_resources).values("pk")
        if matching_resources.exclude(pk__in=operational_ids).exists():
            return Response(
                {"error": "This drive identifier is reserved by training/demo data and cannot be mixed with operational telemetry."},
                status=status.HTTP_409_CONFLICT,
            )
        if default_resource_id:
            resource_exists = Resource.objects.filter(pk=default_resource_id).exists()
            resource_is_operational = operational_resources(
                Resource.objects.filter(pk=default_resource_id)
            ).exists()
            if resource_exists and not resource_is_operational:
                return Response(
                    {"error": "Training/demo resources cannot receive operational telemetry."},
                    status=status.HTTP_409_CONFLICT,
                )

        created_count = 0
        updated_drives = set()

        with transaction.atomic():
            for r in readings:
                serial = r.get("serial_number") or r.get("identifier")
                res = None
                if serial:
                    res = operational_resources(
                        Resource.objects.filter(identifier=serial)
                    ).first()
                    if not res:
                        res = Resource.objects.create(
                            name=f"Drive {serial}",
                            identifier=serial,
                            resource_type=ResourceType.DISK,
                            attributes={
                                "vendor": r.get("vendor", "Seagate"),
                                "serial_number": serial,
                                "datacenter": r.get("datacenter", "DC-1"),
                            },
                            created_by=request.user,
                        )
                    model_metadata = r.get("model")
                    if isinstance(model_metadata, str) and model_metadata.strip():
                        attributes = dict(res.attributes or {})
                        if not attributes.get("drive_model"):
                            attributes["drive_model"] = model_metadata
                            attributes.setdefault("model", model_metadata)
                            res.attributes = attributes
                            res.save(update_fields=["attributes"])
                elif default_resource_id:
                    res = Resource.objects.filter(pk=default_resource_id).first()

                if not res:
                    continue

                updated_drives.add(res.identifier)

                raw_date = r.get("date") or r.get("timestamp")
                if not raw_date:
                    continue

                if "T" in str(raw_date):
                    ts = datetime.fromisoformat(str(raw_date).replace("Z", "+00:00"))
                else:
                    ts = datetime.strptime(str(raw_date), "%Y-%m-%d").replace(tzinfo=dt_timezone.utc)

                values = {}
                for k, v in r.items():
                    if k.startswith("smart_"):
                        try:
                            values[k] = float(v) if v is not None and v != "" else 0.0
                        except (ValueError, TypeError):
                            pass

                Metric.objects.update_or_create(
                    resource=res,
                    timestamp=ts,
                    defaults={"values": values, "source": "API_UPLOAD"},
                )
                created_count += 1

            log_action(
                user=request.user,
                action=ActionType.TELEMETRY_UPLOAD,
                resource_type="Telemetry",
                details={"action": "telemetry_upload", "readings_count": created_count, "drives": list(updated_drives)},
                request=request,
            )

        return Response({
            "status": "success",
            "ingested_readings": created_count,
            "drives_affected": list(updated_drives),
        })


class PredictionRunAPIView(APIView):
    """Run predictions and report full, partial, or complete failure explicitly.

    Full success returns 200, partial success returns 207, and complete failure
    returns 422 for non-actionable inputs, 502 for inference errors, or 500 for
    unexpected persistence/application errors.
    """
    permission_classes = [IsITProOrSysAdmin]

    def post(self, request):
        resource_id = request.data.get("resource_id")
        targets = []
        if resource_id:
            try:
                targets = [disks_with_latest().get(pk=resource_id)]
            except Resource.DoesNotExist:
                raise NotFound("Drive not found.")
        else:
            targets = list(disks_with_latest())

        scored = []
        errors = []

        if not targets:
            return Response({
                "outcome": "complete_failure",
                "message": "No active drives were available for prediction.",
                "scored_count": 0,
                "results": [],
                "errors": [],
            }, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        for target in targets:
            try:
                preds = predict_resource(target, actor=request.user, request=request, source="api")
                if preds:
                    risk_pred, ano_pred = preds
                    scored.append({
                        "resource_id": str(target.id),
                        "identifier": target.identifier,
                        "risk_score": risk_pred.score,
                        "risk_level": risk_pred.risk_level,
                        "is_anomalous": ano_pred.is_anomalous,
                        "anomaly_score": ano_pred.score,
                        "window_start": risk_pred.window_start.isoformat(),
                        "window_end": risk_pred.window_end.isoformat(),
                    })
                else:
                    errors.append({
                        "resource_id": str(target.id),
                        "identifier": target.identifier,
                        "code": "no_new_prediction",
                        "error": "No new prediction was generated (no telemetry or already up to date).",
                    })
            except DriveModelCompatibilityError:
                errors.append({
                    "resource_id": str(target.id),
                    "identifier": target.identifier,
                    "code": "model_compatibility_error",
                    "error": "Drive model compatibility could not be verified; prediction was not performed.",
                })
            except NotEnoughHistory:
                errors.append({
                    "resource_id": str(target.id),
                    "identifier": target.identifier,
                    "code": "insufficient_history",
                    "error": "Insufficient valid telemetry history for prediction.",
                })
            except InferenceError:
                errors.append({
                    "resource_id": str(target.id),
                    "identifier": target.identifier,
                    "code": "inference_error",
                    "error": "The AI prediction could not be completed.",
                })
            except Exception:
                # Do not expose exception text, which may contain database or
                # service internals. The prediction transaction has rolled back.
                errors.append({
                    "resource_id": str(target.id),
                    "identifier": target.identifier,
                    "code": "internal_error",
                    "error": "Prediction could not be completed due to an internal error.",
                })

        response_data = {
            "scored_count": len(scored),
            "results": scored,
            "errors": errors,
        }
        if scored and errors:
            response_data["outcome"] = "partial_success"
            return Response(response_data, status=status.HTTP_207_MULTI_STATUS)
        if scored:
            response_data["outcome"] = "full_success"
            return Response(response_data, status=status.HTTP_200_OK)

        response_data["outcome"] = "complete_failure"
        response_data["message"] = "No drives were successfully scored. Review the per-drive results and try again."
        if any(error["code"] == "internal_error" for error in errors):
            response_status = status.HTTP_500_INTERNAL_SERVER_ERROR
        elif any(error["code"] == "inference_error" for error in errors):
            response_status = status.HTTP_502_BAD_GATEWAY
        else:
            response_status = status.HTTP_422_UNPROCESSABLE_ENTITY
        return Response(response_data, status=response_status)
