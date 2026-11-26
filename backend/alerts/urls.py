from django.urls import path

from .views import (
    AlertAcknowledgeAPIView,
    AlertDetailAPIView,
    AlertListAPIView,
    AlertResolveAPIView,
    AlertUnreadCountAPIView,
)


urlpatterns = [
    path("alerts/", AlertListAPIView.as_view(), name="alerts-list"),
    path("alerts/unread-count/", AlertUnreadCountAPIView.as_view(), name="alerts-unread-count"),
    path("alerts/<str:pk>/", AlertDetailAPIView.as_view(), name="alerts-detail"),
    path("alerts/<str:pk>/acknowledge/", AlertAcknowledgeAPIView.as_view(), name="alerts-acknowledge"),
    path("alerts/<str:pk>/resolve/", AlertResolveAPIView.as_view(), name="alerts-resolve"),
]
