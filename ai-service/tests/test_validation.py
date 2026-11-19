
import pandas as pd

from dp_ml.validation import validate_dataset


def test_validate_empty_dataframe():
    """An empty dataset should return an input validation error."""

    report = validate_dataset(
        df=pd.DataFrame(),
        feature_cols=["smart_5_raw"],
        expected_drive_model="ST12000NM0008",
    )

    assert report["status"] == "invalid"
    assert report["ready_for_prediction"] is False
    assert report["summary"]["errors"] >= 1

    input_check = next(
        check for check in report["checks"]
        if check["name"] == "input"
    )

    assert input_check["status"] == "error"
    assert "no readings" in input_check["message"].lower()

def test_validate_rejects_invalid_column_mapping():
    """Invalid company column mapping should return a validation error."""

    df = pd.DataFrame({
        "date": pd.date_range("2026-01-01", periods=15),
        "company_metric": [10.0] * 15,
    })

    report = validate_dataset(
        df=df,
        feature_cols=["smart_5_raw"],
        expected_drive_model="ST12000NM0008",
        column_mapping={
            "company_metric": "unsupported_feature"
        },
    )

    assert report["status"] == "invalid"
    assert report["ready_for_prediction"] is False

    compatibility_check = next(
        check for check in report["checks"]
        if check["name"] == "column_compatibility"
    )

    assert compatibility_check["status"] == "error"
    assert any(
        "column mapping" in recommendation.lower()
        for recommendation in report["recommendations"]
    )

def test_validate_rejects_multiple_drive_models():
    """A dataset containing multiple drive models should be rejected."""

    df = pd.DataFrame({
        "date": pd.date_range("2026-01-01", periods=15),
        "smart_5_raw": [10.0] * 15,
        "model": ["ST12000NM0008"] * 8 + ["ST8000NM000A"] * 7,
    })

    report = validate_dataset(
        df=df,
        feature_cols=["smart_5_raw"],
        expected_drive_model="ST12000NM0008",
    )

    assert report["status"] == "invalid"

    model_check = next(
        check for check in report["checks"]
        if check["name"] == "drive_model"
    )

    assert model_check["status"] == "error"
    assert "Multiple drive models" in model_check["message"]

def test_validate_warns_when_drive_model_values_are_empty():
    """Empty drive model metadata should produce a warning."""

    df = pd.DataFrame({
        "date": pd.date_range("2026-01-01", periods=15),
        "smart_5_raw": [10.0] * 15,
        "model": [None] * 15,
    })

    report = validate_dataset(
        df=df,
        feature_cols=["smart_5_raw"],
        expected_drive_model="ST12000NM0008",
    )

    model_check = next(
        check for check in report["checks"]
        if check["name"] == "drive_model"
    )

    assert model_check["status"] == "warning"
    assert "No drive model information" in model_check["message"]
    assert report["model_compatibility_verified"] is None

def test_validate_rejects_unsupported_drive_model():
    """An unsupported drive model should fail compatibility validation."""

    df = pd.DataFrame({
        "date": pd.date_range("2026-01-01", periods=15),
        "smart_5_raw": [10.0] * 15,
        "model": ["ST8000NM000A"] * 15,
    })

    report = validate_dataset(
        df=df,
        feature_cols=["smart_5_raw"],
        expected_drive_model="ST12000NM0008",
    )

    assert report["model_compatibility_verified"] is False
    assert report["status"] == "invalid"

    model_check = next(
        check for check in report["checks"]
        if check["name"] == "drive_model"
    )

    assert model_check["status"] == "error"
    assert "not supported" in model_check["message"].lower()

def test_validate_rejects_dataset_with_no_valid_dates():
    """A dataset without valid dates cannot be analyzed."""

    df = pd.DataFrame({
        "date": ["invalid-date"] * 15,
        "smart_5_raw": [10.0] * 15,
        "model": ["ST12000NM0008"] * 15,
    })

    report = validate_dataset(
        df=df,
        feature_cols=["smart_5_raw"],
        expected_drive_model="ST12000NM0008",
    )

    assert report["status"] == "invalid"
    assert report["metrics"]["invalid_dates"] == 15

    date_check = next(
        check for check in report["checks"]
        if check["name"] == "date_coverage"
    )

    assert date_check["status"] == "error"
    assert "No valid dates" in date_check["message"]

def test_validate_warns_when_readings_are_not_chronological():
    """Unsorted readings should produce a date order warning."""

    df = pd.DataFrame({
        "date": pd.date_range(
            "2026-01-01", periods=15
        )[::-1],
        "smart_5_raw": [10.0] * 15,
        "model": ["ST12000NM0008"] * 15,
    })

    report = validate_dataset(
        df=df,
        feature_cols=["smart_5_raw"],
        expected_drive_model="ST12000NM0008",
    )

    date_check = next(
        check for check in report["checks"]
        if check["name"] == "date_order"
    )

    assert date_check["status"] == "warning"
    assert "not chronologically ordered" in date_check["message"]

def test_validate_rejects_duplicate_daily_readings():
    """Multiple readings for the same calendar day should be detected."""

    df = pd.DataFrame({
        "date": [
            "2026-01-01",
            "2026-01-02",
            "2026-01-02",
            "2026-01-03",
            "2026-01-04",
        ],
        "smart_5_raw": [10.0, 11.0, 12.0, 13.0, 14.0],
        "model": ["ST12000NM0008"] * 5,
    })

    report = validate_dataset(
        df=df,
        feature_cols=["smart_5_raw"],
        expected_drive_model="ST12000NM0008",
    )

    assert report["metrics"]["duplicate_dates"] == 1
    assert report["status"] == "invalid"

    duplicate_check = next(
        check for check in report["checks"]
        if check["name"] == "duplicate_dates"
    )

    assert duplicate_check["status"] == "error"
    assert "duplicate daily readings" in duplicate_check["message"].lower()

def test_validate_rejects_non_numeric_smart_values():
    """Non-numeric SMART measurements should be detected."""

    df = pd.DataFrame({
        "date": pd.date_range("2026-01-01", periods=15),
        "smart_5_raw": [10.0] * 14 + ["unknown"],
        "model": ["ST12000NM0008"] * 15,
    })

    report = validate_dataset(
        df=df,
        feature_cols=["smart_5_raw"],
        expected_drive_model="ST12000NM0008",
    )

    assert report["status"] == "invalid"
    assert report["metrics"]["invalid_numeric_values"]["smart_5_raw"] == 1

    numeric_check = next(
        check for check in report["checks"]
        if check["name"] == "numeric_values"
    )

    assert numeric_check["status"] == "error"
    assert "1 non-numeric" in numeric_check["message"]

def test_validate_rejects_negative_smart_values():
    """Negative raw SMART counters should be detected."""

    df = pd.DataFrame({
        "date": pd.date_range("2026-01-01", periods=15),
        "smart_5_raw": [10.0] * 14 + [-5.0],
        "model": ["ST12000NM0008"] * 15,
    })

    report = validate_dataset(
        df=df,
        feature_cols=["smart_5_raw"],
        expected_drive_model="ST12000NM0008",
    )

    assert report["status"] == "invalid"
    assert report["metrics"]["negative_values"]["smart_5_raw"] == 1

    negative_check = next(
        check for check in report["checks"]
        if check["name"] == "negative_values"
    )

    assert negative_check["status"] == "error"
    assert "1 negative SMART values" in negative_check["message"]

def test_validate_warns_about_missing_smart_values():
    """Missing SMART measurements should produce a warning."""

    df = pd.DataFrame({
        "date": pd.date_range("2026-01-01", periods=15),
        "smart_5_raw": [10.0] * 14 + [None],
        "model": ["ST12000NM0008"] * 15,
    })

    report = validate_dataset(
        df=df,
        feature_cols=["smart_5_raw"],
        expected_drive_model="ST12000NM0008",
    )

    assert report["metrics"]["missing_values"]["smart_5_raw"] == 1

    missing_check = next(
        check for check in report["checks"]
        if check["name"] == "missing_values"
    )

    assert missing_check["status"] == "warning"
    assert "1 missing SMART values" in missing_check["message"]

def test_validate_accepts_drive_model_column_alias():
    """Validation should accept drive_model as an alternative to model."""

    df = pd.DataFrame({
        "date": pd.date_range("2026-01-01", periods=15),
        "smart_5_raw": [10.0] * 15,
        "drive_model": ["ST12000NM0008"] * 15,
    })

    report = validate_dataset(
        df=df,
        feature_cols=["smart_5_raw"],
        expected_drive_model="ST12000NM0008",
    )

    assert report["model_compatibility_verified"] is True

    model_check = next(
        check for check in report["checks"]
        if check["name"] == "drive_model"
    )

    assert model_check["status"] == "passed"