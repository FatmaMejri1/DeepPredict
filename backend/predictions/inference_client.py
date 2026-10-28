import json
import os
import urllib.error
import urllib.request


class InferenceError(Exception):
    pass


class NotEnoughHistory(InferenceError):
    pass


INFERENCE_SERVICE_URL = os.getenv("INFERENCE_SERVICE_URL", "http://127.0.0.1:8001")


def predict(readings: list[dict]) -> dict:
    url = f"{INFERENCE_SERVICE_URL.rstrip('/')}/predict"
    payload = json.dumps({"readings": readings}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
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
            raise InferenceError(f"Inference validation error: {detail}")
        raise InferenceError(f"AI service returned HTTP {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise InferenceError(f"Failed to connect to AI service: {exc.reason}") from exc
    except Exception as exc:
        raise InferenceError(f"Inference error: {exc}") from exc
