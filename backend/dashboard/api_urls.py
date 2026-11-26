from django.urls import path

from .api_views import (
    DashboardSummaryAPIView,
    DashboardActivityAPIView,
    DriveDetailAPIView,
    DriveListAPIView,
    DrivePredictionHistoryAPIView,
    DriveTimelineAPIView,
    DriveTelemetryAPIView,
    InferenceServiceHealthAPIView,
    MLModelListAPIView,
    PredictionRunAPIView,
    TelemetryUploadAPIView,
    TelemetryValidateAPIView,
)

urlpatterns = [
    path("dashboard/summary/", DashboardSummaryAPIView.as_view(), name="api-dashboard-summary"),
    path("dashboard/activity/", DashboardActivityAPIView.as_view(), name="api-dashboard-activity"),
    path("dashboard/health/", InferenceServiceHealthAPIView.as_view(), name="api-dashboard-health"),
    path("drives/", DriveListAPIView.as_view(), name="api-drives-list"),
    path("drives/<uuid:pk>/", DriveDetailAPIView.as_view(), name="api-drives-detail"),
    path("drives/<uuid:pk>/telemetry/", DriveTelemetryAPIView.as_view(), name="api-drives-telemetry"),
    path("drives/<uuid:pk>/predictions/", DrivePredictionHistoryAPIView.as_view(), name="api-drives-predictions"),
    path("drives/<uuid:pk>/timeline/", DriveTimelineAPIView.as_view(), name="api-drives-timeline"),
    path("ml-models/", MLModelListAPIView.as_view(), name="api-ml-models"),
    path("telemetry/validate/", TelemetryValidateAPIView.as_view(), name="api-telemetry-validate"),
    path("telemetry/upload/", TelemetryUploadAPIView.as_view(), name="api-telemetry-upload"),
    path("predictions/predict/", PredictionRunAPIView.as_view(), name="api-predictions-predict"),
]
