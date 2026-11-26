
import pandas as pd
import pytest

from service.app import predictor


@pytest.mark.parametrize(
    "level, expected",
    [
        ("medium", "MEDIUM"),
        ("high", "HIGH"),
        ("critical", "CRITICAL"),
    ],
)
def test_risk_level_thresholds(level, expected):
    threshold = predictor.cfg["thresholds"]["risk"][level]

    result = predictor.risk_level(threshold)

    assert result == expected


def test_predict_returns_none_with_insufficient_history():
    feature_cols = predictor.cfg["feature_cols"]

    df = pd.DataFrame({
        "date": pd.date_range("2026-01-01", periods=10),
        **{
            col: [1.0] * 10
            for col in feature_cols
        },
    })

    result = predictor.predict(df)

    assert result is None
