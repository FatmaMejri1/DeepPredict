from django.apps import AppConfig


class DashboardConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "dashboard"

    def ready(self):
        # Attach OWASP security headers to static files served by django.views.static.serve
        try:
            from django.views import static as django_views_static

            if not getattr(django_views_static, "_deeppredict_security_patched", False):
                _orig_serve = django_views_static.serve

                def _secure_static_serve(*args, **kwargs):
                    response = _orig_serve(*args, **kwargs)
                    response["X-Content-Type-Options"] = "nosniff"
                    response["Server"] = "DeepPredict"
                    response["Content-Security-Policy"] = (
                        "default-src 'self'; "
                        "script-src 'self' 'unsafe-inline'; "
                        "style-src 'self' 'unsafe-inline'; "
                        "img-src 'self' data:; "
                        "font-src 'self'; "
                        "connect-src 'self'; "
                        "frame-ancestors 'none'; "
                        "form-action 'self'; "
                        "base-uri 'self'; "
                        "object-src 'none'"
                    )
                    return response

                django_views_static.serve = _secure_static_serve
                django_views_static._deeppredict_security_patched = True
        except Exception:
            pass
