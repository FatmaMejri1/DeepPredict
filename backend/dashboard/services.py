import json
from datetime import timezone as dt_timezone
from urllib.error import URLError
from urllib.request import Request, urlopen

from django.utils import timezone

from predictions.inference_client import INFERENCE_SERVICE_URL


AI_HEALTH_TIMEOUT_SECONDS = 2


def inference_service_health():
    """Return a safe status snapshot from the configured FastAPI health route."""
    checked_at = timezone.now().astimezone(dt_timezone.utc).isoformat()
    health_url = f"{INFERENCE_SERVICE_URL.rstrip('/')}/health"
    request = Request(health_url, headers={"Accept": "application/json"})

    try:
        with urlopen(request, timeout=AI_HEALTH_TIMEOUT_SECONDS) as response:
            if response.status != 200:
                raise URLError(f"Health endpoint returned {response.status}")
            payload = json.loads(response.read().decode("utf-8"))
    except (URLError, TimeoutError, OSError, ValueError):
        return {"status": "offline", "model_version": None, "checked_at": checked_at}

    if not isinstance(payload, dict) or payload.get("status") != "ok":
        return {"status": "offline", "model_version": None, "checked_at": checked_at}

    return {
        "status": "online",
        "model_version": payload.get("model_version"),
        "checked_at": checked_at,
    }
