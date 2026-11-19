
import numpy as np
import pandas as pd

from dp_ml.preprocess import (
    fill_drive,
    make_windows_for_drive,
    window_for_inference,
    to_log_space,
)


FEATURES = ["smart_5_raw", "smart_197_raw"]


def create_drive(days=20):
    dates = pd.date_range("2026-01-01", periods=days, freq="D")

    return pd.DataFrame({
        "date": dates,
        "smart_5_raw": np.arange(days, dtype=float),
        "smart_197_raw": np.arange(days, dtype=float) + 10,
    })


def test_fill_drive_creates_daily_calendar():
    df = create_drive()
    df = df.drop(index=[3])

    dates, feats = fill_drive(df, FEATURES)

    assert len(dates) == 20
    assert feats.shape == (20, 3)
    assert feats[3, -1] == 1
    assert feats[2, -1] == 0


def test_fill_drive_keeps_long_gaps_as_nan():
    df = create_drive()
    df = df.drop(index=[3, 4, 5, 6])

    dates, feats = fill_drive(df, FEATURES)

    # First 3 missing days are forward-filled
    assert not np.isnan(feats[3, 0])
    assert not np.isnan(feats[4, 0])
    assert not np.isnan(feats[5, 0])

    # Fourth missing day remains NaN
    assert np.isnan(feats[6, 0])


def test_make_windows_for_drive_without_failure():
    df = create_drive()

    windows, labels = make_windows_for_drive(
        df, None, FEATURES, window=14
    )

    assert len(windows) == 7
    assert all(label == 0 for label in labels)
    assert windows[0].shape == (14, 3)


def test_make_windows_for_drive_with_failure():
    df = create_drive()
    fail_date = pd.Timestamp("2026-01-20")

    windows, labels = make_windows_for_drive(
        df, fail_date, FEATURES, window=14, horizon=7
    )

    assert len(windows) > 0
    assert 1 in labels


def test_window_for_inference_with_valid_history():
    df = create_drive()

    result = window_for_inference(df, FEATURES, window=14)

    assert result is not None

    window, start, end = result

    assert window.shape == (14, 3)
    assert start == pd.Timestamp("2026-01-07")
    assert end == pd.Timestamp("2026-01-20")


def test_window_for_inference_with_insufficient_history():
    df = create_drive(days=10)

    result = window_for_inference(df, FEATURES, window=14)

    assert result is None


def test_to_log_space_transforms_values():
    values = np.array([0, 1, 9], dtype=float)

    result = to_log_space(values)

    assert result.dtype == np.float32
    assert np.allclose(result, np.log1p(values))

def test_make_windows_skips_windows_with_unfillable_gaps():
    df = create_drive()
    df = df.drop(index=[3, 4, 5, 6])

    windows, labels = make_windows_for_drive(
        df, None, FEATURES, window=14
    )

    # Windows containing the unfillable gap must be skipped
    assert len(windows) == 0


def test_make_windows_skips_windows_after_failure_date():
    df = create_drive()
    fail_date = pd.Timestamp("2026-01-10")

    windows, labels = make_windows_for_drive(
        df, fail_date, FEATURES, window=14
    )

    assert len(windows) == 0


def test_window_for_inference_rejects_unfillable_gap():
    df = create_drive()
    df.loc[16, "smart_5_raw"] = np.nan
    df.loc[17, "smart_5_raw"] = np.nan
    df.loc[18, "smart_5_raw"] = np.nan
    df.loc[19, "smart_5_raw"] = np.nan

    result = window_for_inference(df, FEATURES, window=14)

    assert result is None


def test_to_log_space_clips_negative_values():
    values = np.array([-5, 0, 9], dtype=float)

    result = to_log_space(values)

    expected = np.log1p([0, 0, 9]).astype(np.float32)

    assert np.allclose(result, expected)

def test_make_windows_for_failure_beyond_horizon():
    df = create_drive()
    fail_date = pd.Timestamp("2026-01-30")

    windows, labels = make_windows_for_drive(
        df,
        fail_date,
        FEATURES,
        window=14,
        horizon=7,
    )

    assert len(windows) > 0
    assert all(label == 0 for label in labels)
