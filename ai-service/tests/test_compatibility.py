
import pandas as pd
import pytest

from dp_ml.compatibility import normalize_name, normalize_columns


FEATURES = ["smart_5_raw", "smart_197_raw"]


def create_company_data():
    return pd.DataFrame({
        "timestamp": pd.date_range("2026-01-01", periods=3),
        "smart5": [1, 2, 3],
        "pending_sectors": [0, 1, 0],
    })


def test_normalize_name():
    assert normalize_name("SMART-5 Raw") == "smart5raw"


def test_normalize_columns_supports_date_alias():
    df = create_company_data()

    result = normalize_columns(df, FEATURES)

    assert "date" in result.columns
    assert "smart_5_raw" in result.columns
    assert "smart_197_raw" in result.columns


def test_normalize_columns_rejects_missing_date():
    df = pd.DataFrame({
        "smart_5_raw": [1, 2],
        "smart_197_raw": [0, 1],
    })

    with pytest.raises(ValueError, match="No date column"):
        normalize_columns(df, FEATURES)


def test_normalize_columns_rejects_missing_mapping_source():
    df = create_company_data()

    with pytest.raises(ValueError, match="does not exist"):
        normalize_columns(
            df,
            FEATURES,
            column_mapping={"unknown_column": "smart_5_raw"},
        )


def test_normalize_columns_rejects_unsupported_target():
    df = create_company_data()

    with pytest.raises(ValueError, match="not a supported model feature"):
        normalize_columns(
            df,
            FEATURES,
            column_mapping={"smart5": "smart_999_raw"},
        )


def test_normalize_columns_rejects_existing_target():
    df = pd.DataFrame({
        "date": pd.date_range("2026-01-01", periods=3),
        "smart_5_raw": [1, 2, 3],
        "company_smart5": [4, 5, 6],
        "smart_197_raw": [0, 1, 0],
    })

    with pytest.raises(ValueError, match="target column already exists"):
        normalize_columns(
            df,
            FEATURES,
            column_mapping={"company_smart5": "smart_5_raw"},
        )

def test_normalize_columns_rejects_ambiguous_aliases():
    df = pd.DataFrame({
        "date": pd.date_range("2026-01-01", periods=2),
        "smart_5": [1, 2],
        "smart5": [3, 4],
        "pending_sectors": [0, 1],
    })

    with pytest.raises(ValueError, match="Multiple columns"):
        normalize_columns(df, FEATURES)


def test_normalize_columns_allows_missing_features_when_optional():
    df = pd.DataFrame({
        "date": pd.date_range("2026-01-01", periods=2),
        "smart_5": [1, 2],
    })

    result = normalize_columns(
        df,
        FEATURES,
        require_all_features=False,
    )

    assert "smart_5_raw" in result.columns
    assert "smart_197_raw" not in result.columns


def test_normalize_columns_rejects_missing_required_features():
    df = pd.DataFrame({
        "date": pd.date_range("2026-01-01", periods=2),
        "smart_5": [1, 2],
    })

    with pytest.raises(ValueError, match="Missing required SMART features"):
        normalize_columns(df, FEATURES)


def test_normalize_columns_supports_explicit_date_mapping():
    df = pd.DataFrame({
        "measurement_day": pd.date_range("2026-01-01", periods=2),
        "smart_5": [1, 2],
        "pending_sectors": [0, 1],
    })

    result = normalize_columns(
        df,
        FEATURES,
        column_mapping={"measurement_day": "date"},
    )

    assert "date" in result.columns
    assert "measurement_day" not in result.columns

def test_normalize_columns_keeps_canonical_column_with_explicit_mapping():
    df = pd.DataFrame({
        "date": pd.date_range("2026-01-01", periods=3),
        "smart_5_raw": [1, 2, 3],
        "smart_197_raw": [0, 1, 0],
    })

    result = normalize_columns(
        df,
        FEATURES,
        column_mapping={"smart_5_raw": "smart_5_raw"},
    )

    assert "smart_5_raw" in result.columns
    assert result["smart_5_raw"].tolist() == [1, 2, 3]

def test_normalize_columns_supports_feature_without_smart_pattern():
    features = ["custom_metric"]
    df = pd.DataFrame({
        "date": pd.date_range("2026-01-01", periods=2),
        "custom_metric": [10, 20],
    })

    result = normalize_columns(df, features)

    assert "custom_metric" in result.columns
    assert result["custom_metric"].tolist() == [10, 20]
