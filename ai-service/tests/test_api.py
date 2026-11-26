
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from service.app import app


# Project paths
BASE_DIR = Path(__file__).resolve().parents[1]

# Load the real test payload
with open(BASE_DIR / "test_payload.json", "r", encoding="utf-8") as file:
    PAYLOAD = json.load(file)


client = TestClient(app)


def test_health_endpoint():
    """The API should report that the service is healthy."""

    response = client.get("/health")

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "ok"
    assert data["model_version"] == "gru-ae-v1"


def test_validate_endpoint_with_valid_data():
    """Valid drive data should pass validation."""

    payload = json.loads(json.dumps(PAYLOAD))

    for reading in payload["readings"]:
        reading["model"] = "ST12000NM0008"

    response = client.post("/validate", json=payload)

    assert response.status_code == 200

    report = response.json()

    assert report["status"] == "valid"
    assert report["ready_for_prediction"] is True
    assert report["model_compatibility_verified"] is True
    assert report["history_valid"] is True


def test_predict_endpoint_with_valid_data():
    """Valid compatible data should produce an AI prediction."""

    payload = json.loads(json.dumps(PAYLOAD))

    for reading in payload["readings"]:
        reading["model"] = "ST12000NM0008"

    response = client.post("/predict", json=payload)

    assert response.status_code == 200

    prediction = response.json()

    assert 0 <= prediction["risk_score"] <= 1
    assert prediction["risk_level"] in [
        "LOW", "MEDIUM", "HIGH", "CRITICAL"
    ]
    assert prediction["horizon_days"] == 7
    assert prediction["anomaly_score"] >= 0
    assert prediction["model_version"] == "gru-ae-v1"


def test_predict_rejects_unsupported_drive_model():
    """An unsupported HDD model must not reach AI inference."""

    payload = json.loads(json.dumps(PAYLOAD))

    for reading in payload["readings"]:
        reading["model"] = "ST8000NM000A"

    response = client.post("/predict", json=payload)

    assert response.status_code == 422

    detail = response.json()["detail"]

    assert detail["validation_report"]["model_compatibility_verified"] is False
    assert detail["validation_report"]["ready_for_prediction"] is False


def test_validate_rejects_empty_readings():
    """An empty dataset must be rejected."""

    response = client.post(
        "/validate",
        json={"readings": []}
    )

    assert response.status_code == 422

def test_validate_without_drive_model_returns_warning():
    """Validation should warn when drive model metadata is absent."""

    payload = json.loads(json.dumps(PAYLOAD))

    for reading in payload["readings"]:
        reading.pop("model", None)

    response = client.post("/validate", json=payload)

    assert response.status_code == 200

    report = response.json()

    assert report["status"] == "warning"
    assert report["model_compatibility_verified"] is None
    assert report["ready_for_prediction"] is True


def test_predict_rejects_missing_drive_model():
    """Prediction must reject data when drive compatibility is unverified."""

    payload = json.loads(json.dumps(PAYLOAD))

    for reading in payload["readings"]:
        reading.pop("model", None)

    response = client.post("/predict", json=payload)

    assert response.status_code == 422

    report = response.json()["detail"]["validation_report"]

    assert report["model_compatibility_verified"] is None


def test_predict_rejects_missing_smart_feature():
    """Prediction must reject datasets missing a required SMART feature."""

    payload = json.loads(json.dumps(PAYLOAD))

    for reading in payload["readings"]:
        reading["model"] = "ST12000NM0008"
        reading.pop("smart_240_raw", None)

    response = client.post("/predict", json=payload)

    assert response.status_code == 422


def test_predict_rejects_invalid_date():
    """Prediction must reject invalid date values."""

    payload = json.loads(json.dumps(PAYLOAD))

    for reading in payload["readings"]:
        reading["model"] = "ST12000NM0008"

    payload["readings"][0]["date"] = "2026-99-45"

    response = client.post("/predict", json=payload)

    assert response.status_code == 422


def test_predict_rejects_insufficient_history():
    """Prediction must reject datasets with fewer than 14 days."""

    payload = json.loads(json.dumps(PAYLOAD))
    payload["readings"] = payload["readings"][:10]

    for reading in payload["readings"]:
        reading["model"] = "ST12000NM0008"

    response = client.post("/predict", json=payload)

    assert response.status_code == 422


def test_predict_supports_explicit_column_mapping():
    """Company-specific SMART column names should be supported."""

    payload = json.loads(json.dumps(PAYLOAD))

    for reading in payload["readings"]:
        reading["model"] = "ST12000NM0008"
        reading["company_reallocated_count"] = reading.pop("smart_5_raw")
        reading["company_pending_sector_count"] = reading.pop("smart_197_raw")

    payload["column_mapping"] = {
        "company_reallocated_count": "smart_5_raw",
        "company_pending_sector_count": "smart_197_raw"
    }

    response = client.post("/predict", json=payload)

    assert response.status_code == 200

    prediction = response.json()

    assert prediction["model_version"] == "gru-ae-v1"
    assert prediction["risk_level"] in [
        "LOW", "MEDIUM", "HIGH", "CRITICAL"
    ]
def test_predict_rejects_empty_readings():
    """Prediction must reject an empty dataset."""

    response = client.post(
        "/predict",
        json={"readings": []}
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "readings is empty"
def test_validate_converts_value_error_to_http_422(monkeypatch):
    """Validation ValueErrors should be returned as HTTP 422."""

    def raise_value_error(*args, **kwargs):
        raise ValueError("Invalid validation input")

    monkeypatch.setattr(
        "service.app.validate_dataset",
        raise_value_error
    )

    response = client.post(
        "/validate",
        json={"readings": [{"date": "2026-01-01"}]}
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Invalid validation input"

def test_predict_rejects_invalid_date_after_validation(monkeypatch):
    """Prediction should reject invalid dates after initial validation."""

    from service.app import predictor

    def fake_validate_dataset(*args, **kwargs):
        return {
            "ready_for_prediction": True,
            "history_valid": True,
            "model_compatibility_verified": True,
            "status": "valid"
        }

    monkeypatch.setattr(
        "service.app.validate_dataset",
        fake_validate_dataset
    )

    monkeypatch.setattr(
        "service.app.normalize_columns",
        lambda df, **kwargs: df
    )

    payload = {
        "readings": [
            {"date": "not-a-valid-date"}
        ]
    }

    response = client.post("/predict", json=payload)

    assert response.status_code == 422
    assert response.json()["detail"] == "Some date values are invalid."

def test_predict_rejects_none_prediction(monkeypatch):
    """API should reject prediction when the model returns None."""

    from service.app import predictor

    def fake_validate_dataset(*args, **kwargs):
        return {
            "ready_for_prediction": True,
            "history_valid": True,
            "model_compatibility_verified": True,
            "status": "valid"
        }

    monkeypatch.setattr(
        "service.app.validate_dataset",
        fake_validate_dataset
    )

    monkeypatch.setattr(
        "service.app.normalize_columns",
        lambda df, **kwargs: df
    )

    monkeypatch.setattr(
        predictor,
        "predict",
        lambda df: None
    )

    payload = {
        "readings": [
            {"date": "2026-01-01"}
        ]
    }

    response = client.post("/predict", json=payload)

    assert response.status_code == 422

    assert "Not enough valid history" in response.json()["detail"]

def test_predict_converts_value_error_to_http_422(monkeypatch):
    """Prediction ValueErrors should be returned as HTTP 422."""

    def raise_value_error(*args, **kwargs):
        raise ValueError("Invalid prediction input")

    monkeypatch.setattr(
        "service.app.validate_dataset",
        raise_value_error
    )

    response = client.post(
        "/predict",
        json={"readings": [{"date": "2026-01-01"}]}
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Invalid prediction input"

def test_predict_handles_missing_smart_values_through_pipeline():
    """The complete prediction pipeline should handle a missing SMART value."""

    payload = json.loads(json.dumps(PAYLOAD))

    for reading in payload["readings"]:
        reading["model"] = "ST12000NM0008"

    # Simulate one missing SMART reading.
    payload["readings"][7]["smart_5_raw"] = None

    response = client.post("/predict", json=payload)

    assert response.status_code == 200

    prediction = response.json()

    assert 0 <= prediction["risk_score"] <= 1
    assert prediction["risk_level"] in [
        "LOW", "MEDIUM", "HIGH", "CRITICAL"
    ]
    assert prediction["anomaly_score"] >= 0


def test_predict_rejects_unfillable_date_gap():
    """The API must reject a four-day gap inside the inference window."""

    payload = json.loads(json.dumps(PAYLOAD))

    for reading in payload["readings"]:
        reading["model"] = "ST12000NM0008"

    # Remove four consecutive days but preserve the full 14-day date range.
    payload["readings"] = [
        reading
        for i, reading in enumerate(payload["readings"])
        if i not in [5, 6, 7, 8]
    ]

    response = client.post("/predict", json=payload)

    assert response.status_code == 422

    detail = response.json()["detail"]
    report = detail["validation_report"]

    print(json.dumps(report, indent=2))

    assert report["ready_for_prediction"] is False
    assert report["history_valid"] is False
    assert report["metrics"]["max_consecutive_gap"] == 4

    assert any(
        check["name"] == "historical_coverage"
        and check["status"] == "error"
        for check in report["checks"]
    )
