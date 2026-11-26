from .models import ActionType, AuditLog


def get_client_ip(request):
    """Extract client IP address from HTTP request."""
    if not request:
        return None
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0].strip()
    else:
        ip = request.META.get("REMOTE_ADDR")
    return ip


def log_action(
    action: str,
    user=None,
    resource_type: str = "",
    resource_id: str = "",
    details: dict = None,
    request=None,
    ip_address: str = None,
):
    """
    Record an immutable audit log entry.
    """
    if details is None:
        details = {}

    # Extract user and IP from request if provided and not explicitly specified
    if request:
        if user is None and hasattr(request, "user") and request.user.is_authenticated:
            user = request.user
        if ip_address is None:
            ip_address = get_client_ip(request)

    username = ""
    if user:
        if isinstance(user, str):
            username = user
            user_obj = None
        else:
            user_obj = user
            username = getattr(user, "username", str(user))
    else:
        user_obj = None

    # Callers that require a durable audit trail must be able to fail their
    # surrounding transaction when this insert fails. Best-effort callers,
    # such as authentication signals, handle exceptions at their boundary.
    return AuditLog.objects.create(
        user=user_obj,
        username=username,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id) if resource_id is not None else "",
        ip_address=ip_address,
        details=details,
    )
