import logging

from django.contrib.auth import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver
from .models import ActionType
from .services import get_client_ip, log_action

logger = logging.getLogger("audit")


def _log_auth_action(**kwargs):
    """Authentication audit events are best-effort and must not block auth."""
    try:
        log_action(**kwargs)
    except Exception:
        logger.exception("Failed to write best-effort authentication audit event")


@receiver(user_logged_in)
def on_user_logged_in(sender, request, user, **kwargs):
    ip = get_client_ip(request)
    _log_auth_action(
        action=ActionType.LOGIN_SUCCESS,
        user=user,
        resource_type="auth",
        resource_id=str(user.pk),
        details={"message": f"User {user.username} logged in successfully."},
        ip_address=ip,
    )


@receiver(user_logged_out)
def on_user_logged_out(sender, request, user, **kwargs):
    ip = get_client_ip(request)
    _log_auth_action(
        action=ActionType.LOGOUT,
        user=user,
        resource_type="auth",
        resource_id=str(user.pk) if user else "",
        details={"message": f"User {getattr(user, 'username', 'Unknown')} logged out."},
        ip_address=ip,
    )


@receiver(user_login_failed)
def on_user_login_failed(sender, credentials, request, **kwargs):
    ip = get_client_ip(request)
    attempted_username = credentials.get("username", "<empty>") if credentials else "<unknown>"
    _log_auth_action(
        action=ActionType.LOGIN_FAILED,
        user=attempted_username,
        resource_type="auth",
        resource_id="",
        details={"attempted_username": attempted_username, "message": "Failed login attempt."},
        ip_address=ip,
    )
