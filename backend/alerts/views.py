import logging
from uuid import UUID

from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsITProOrSysAdmin
from audit.models import ActionType
from audit.services import log_action
from infrastructure.models import Resource
from infrastructure.operational import operational_resources

from .models import Alert, AlertSeverity, AlertStatus, AlertType
from .serializers import AlertSerializer


logger = logging.getLogger(__name__)


class AlertPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


def alert_queryset():
    return Alert.objects.filter(
        resource_id__in=operational_resources().values("pk")
    ).select_related(
        "resource",
        "latest_prediction",
        "latest_prediction__model_version",
        "acknowledged_by",
        "resolved_by",
    )


def parse_alert_uuid(value):
    try:
        return UUID(str(value))
    except (TypeError, ValueError, AttributeError):
        return None


class AlertListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = alert_queryset()
        choice_filters = (
            ("status", "status", AlertStatus.values),
            ("alert_type", "alert_type", AlertType.values),
            ("severity", "severity", AlertSeverity.values),
        )
        for parameter, field, choices in choice_filters:
            if parameter in request.query_params:
                value = request.query_params[parameter]
                if value not in choices:
                    return Response(
                        {"detail": f"Invalid {parameter} filter.", "field": parameter},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                queryset = queryset.filter(**{field: value})

        if "resource" in request.query_params:
            value = request.query_params["resource"]
            try:
                resource_id = UUID(value)
            except (TypeError, ValueError, AttributeError):
                return Response(
                    {"detail": "The resource filter must be a valid UUID.", "field": "resource"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            queryset = queryset.filter(resource_id=resource_id)

        queryset = queryset.order_by("-updated_at", "-created_at", "-id")
        paginator = AlertPagination()
        page = paginator.paginate_queryset(queryset, request)
        return paginator.get_paginated_response(AlertSerializer(page, many=True).data)


class AlertUnreadCountAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({"count": alert_queryset().filter(status=AlertStatus.OPEN).count()})


class AlertDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        alert_id = parse_alert_uuid(pk)
        if alert_id is None:
            return Response({"detail": "Alert not found."}, status=status.HTTP_404_NOT_FOUND)
        try:
            alert = alert_queryset().get(pk=alert_id)
        except Alert.DoesNotExist:
            return Response({"detail": "Alert not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(AlertSerializer(alert).data)


class AlertActionAPIView(APIView):
    permission_classes = [IsITProOrSysAdmin]

    action = None

    def post(self, request, pk):
        alert_id = parse_alert_uuid(pk)
        if alert_id is None:
            return Response({"detail": "Alert not found."}, status=status.HTTP_404_NOT_FOUND)
        try:
            resource_id = Alert.objects.filter(pk=alert_id).values_list(
                "resource_id", flat=True
            ).first()
            if resource_id is None:
                return Response({"detail": "Alert not found."}, status=status.HTTP_404_NOT_FOUND)

            with transaction.atomic():
                # Match prediction persistence lock order: Resource, then Alert.
                Resource.objects.select_for_update().get(pk=resource_id)
                alert = (
                    alert_queryset()
                    .filter(resource_id=resource_id)
                    .select_for_update(of=("self",))
                    .select_related(
                        "resource",
                        "latest_prediction",
                        "latest_prediction__model_version",
                        "acknowledged_by",
                        "resolved_by",
                    )
                    .get(pk=alert_id)
                )

                if self.action == "acknowledge":
                    if alert.status == AlertStatus.ACKNOWLEDGED:
                        return Response(AlertSerializer(alert).data)
                    if alert.status != AlertStatus.OPEN:
                        return Response(
                            {"detail": "Only open alerts can be acknowledged."},
                            status=status.HTTP_409_CONFLICT,
                        )
                    alert.status = AlertStatus.ACKNOWLEDGED
                    alert.acknowledged_at = timezone.now()
                    alert.acknowledged_by = request.user
                    update_fields = ("status", "acknowledged_at", "acknowledged_by", "updated_at")
                else:
                    if alert.status == AlertStatus.RESOLVED:
                        return Response(
                            {"detail": "This alert is already resolved."},
                            status=status.HTTP_409_CONFLICT,
                        )
                    alert.status = AlertStatus.RESOLVED
                    alert.resolved_at = timezone.now()
                    alert.resolved_by = request.user
                    alert.resolution_source = "USER"
                    update_fields = ("status", "resolved_at", "resolved_by", "resolution_source", "updated_at")

                alert.save(update_fields=update_fields)
                log_action(
                    action=ActionType.UPDATE,
                    user=request.user,
                    request=request,
                    resource_type="Alert",
                    resource_id=str(alert.pk),
                    details={
                        "action": self.action,
                        "resource_id": str(alert.resource_id),
                        "source": "alerts_api",
                    },
                )
        except Alert.DoesNotExist:
            return Response({"detail": "Alert not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception:
            logger.exception("Alert lifecycle action failed.")
            return Response(
                {"detail": "The alert action could not be completed."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        alert = alert_queryset().get(pk=alert_id)
        return Response(AlertSerializer(alert).data)


class AlertAcknowledgeAPIView(AlertActionAPIView):
    action = "acknowledge"


class AlertResolveAPIView(AlertActionAPIView):
    action = "resolve"
