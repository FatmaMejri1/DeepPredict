from django.contrib import admin
from django.http import HttpResponse
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerSplitView

admin.site.site_header = "DeepPredict Administration"
admin.site.site_title = "DeepPredict Admin"
admin.site.index_title = "Admin Dashboard"


def robots_txt(request):
    content = "User-agent: *\nDisallow: /admin/\nDisallow: /api/\n"
    return HttpResponse(content, content_type="text/plain; charset=utf-8")


urlpatterns = [
    path("robots.txt", robots_txt, name="robots_txt"),
    path("admin/", admin.site.urls),
    path("api/", include("accounts.urls")),
    path("api/", include("dashboard.api_urls")),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerSplitView.as_view(url_name="schema"), name="docs"),
]