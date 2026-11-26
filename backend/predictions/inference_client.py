
import json
import os
import urllib.error
import urllib.request
from urllib.parse import urlsplit


class InferenceError(Exception):
    pass


class NotEnoughHistory(InferenceError):
    pass


INFERENCE_SERVICE_URL = os.getenv(
    "INFERENCE_SERVICE_URL",
    "http://127.0.0.1:8001",
)


def _validate_service_url(url: str) -> str:
    """Allow only HTTP/HTTPS URLs with a valid hostname."""
    try:
        parsed = urlsplit(url)

        if parsed.scheme not in ("http", "https"):
            raise ValueError("Only HTTP and HTTPS schemes are allowed.")

        if not parsed.hostname:
            raise ValueError("Inference service URL must contain a hostname.")

        if parsed.username or parsed.password:
            raise ValueError("Credentials must not be embedded in the service URL.")

        if parsed.query or parsed.fragment:
            raise ValueError("Query strings and fragments are not allowed.")

        parsed.port  # Validate the port if one is specified.

        return url.rstrip("/") + "/predict"

    except ValueError as exc:
        raise InferenceError(f"Invalid inference service URL: {exc}") from exc


def predict(readings: list[dict]) -> dict:
    url = _validate_service_url(INFERENCE_SERVICE_URL)

    payload = json.dumps({"readings": readings}).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        # URL validated by _validate_service_url before the request.
        with urllib.request.urlopen(req, timeout=30) as resp:  # nosec B310
            data = resp.read().decode("utf-8")
            return json.loads(data)

    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")

        if exc.code == 422:
            try:
                detail = json.loads(body).get("detail", body)
            except Exception:
                detail = body

            if "not enough valid history" in str(detail).lower():
                raise NotEnoughHistory(detail)

            raise InferenceError(
                f"Inference validation error: {detail}"
            )

        raise InferenceError(
            f"AI service returned HTTP {exc.code}: {body}"
        ) from exc

    except urllib.error.URLError as exc:
        raise InferenceError(
            f"Failed to connect to AI service: {exc.reason}"
        ) from exc

    except Exception as exc:
        raise InferenceError(f"Inference error: {exc}") from exc
