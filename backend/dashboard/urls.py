from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.summary, name="summary"),
    path("drives/", views.resource_list, name="resources"),
    path("drives/<uuid:pk>/", views.resource_detail, name="resource_detail"),
    path("models/", views.models_page, name="models"),
    path("login/", views.RoleBasedLoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
]
