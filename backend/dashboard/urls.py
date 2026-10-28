from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.summary, name="summary"),
    path("drives/", views.resource_list, name="resources"),
    path("drives/<uuid:pk>/", views.resource_detail, name="resource_detail"),
    path("models/", views.models_page, name="models"),
    path("login/", auth_views.LoginView.as_view(
        template_name="dashboard/login.html", redirect_authenticated_user=True), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
]
