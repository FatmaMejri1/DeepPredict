"""
Views for audit application.
Audit logging events are captured and recorded via signals and services.
"""
from datetime import datetime, time, timedelta

from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Role
from .models import ActionType, AuditLog
from .serializers import AuditLogSerializer


class IsActiveStaffSysAdmin(BasePermission):
    """Require the full Django staff and DeepPredict SYSADMIN identity."""

    message = "Only active SYSADMIN staff users can access audit records."

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and user.is_active
            and user.is_staff
            and user.role == Role.SYSADMIN
        )


class AuditLogPagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 100


class AuditLogListAPIView(APIView):
    permission_classes = [IsAuthenticated, IsActiveStaffSysAdmin]
    http_method_names = ["get", "head", "options"]

    def get(self, request):
        queryset = AuditLog.objects.select_related("user").all()

        username = request.query_params.get("username", "").strip()
        if username:
            queryset = queryset.filter(
                Q(username__icontains=username) | Q(user__username__icontains=username)
            )

        action = request.query_params.get("action", "").strip()
        if action:
            if action not in ActionType.values:
                return Response(
                    {"detail": "Invalid action filter.", "field": "action"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            queryset = queryset.filter(action=action)

        date_from = request.query_params.get("date_from", "").strip()
        date_to = request.query_params.get("date_to", "").strip()
        try:
            parsed_from = parse_date(date_from) if date_from else None
            parsed_to = parse_date(date_to) if date_to else None
        except ValueError:
            parsed_from = parsed_to = None
        if (date_from and parsed_from is None) or (date_to and parsed_to is None):
            return Response(
                {"detail": "Dates must use YYYY-MM-DD format.", "field": "date_range"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if parsed_from and parsed_to and parsed_from > parsed_to:
            return Response(
                {"detail": "date_from must be on or before date_to.", "field": "date_range"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if parsed_from:
            start = timezone.make_aware(datetime.combine(parsed_from, time.min))
            queryset = queryset.filter(timestamp__gte=start)
        if parsed_to:
            end = timezone.make_aware(datetime.combine(parsed_to + timedelta(days=1), time.min))
            queryset = queryset.filter(timestamp__lt=end)

        queryset = queryset.order_by("-timestamp", "-id")
        paginator = AuditLogPagination()
        page = paginator.paginate_queryset(queryset, request)
        return paginator.get_paginated_response(AuditLogSerializer(page, many=True).data)
