import numpy as np
import pandas as pd

WINDOW = 14
HORIZON = 7
MAX_FILL = 3


def fill_drive(df_drive, feature_cols, max_fill=MAX_FILL):
    # Put one drive on a full daily calendar and forward-fill short gaps.
    # Returns (dates, feats): feats has len(feature_cols)+1 columns, the last one is
    # gap_filled (1 = the day was filled). NaN remains where a gap is longer than max_fill.
    df_drive = df_drive.sort_values("date")
    full = pd.date_range(df_drive["date"].min(), df_drive["date"].max())
    observed = full.isin(df_drive["date"]).astype(np.float32)
    d = df_drive.set_index("date")[list(feature_cols)].reindex(full).ffill(limit=max_fill)
    feats = np.concatenate([d.values.astype(np.float32), (1 - observed)[:, None]], axis=1)
    return full.values, feats


def make_windows_for_drive(df_drive, fail_date, feature_cols, window=WINDOW,
                           horizon=HORIZON, stride=1, max_fill=MAX_FILL):
    dates, feats = fill_drive(df_drive, feature_cols, max_fill)
    valid = ~np.isnan(feats).any(axis=1)
    bad_cum = np.concatenate([[0], np.cumsum(~valid)])
    n = len(dates)
    windows, labels = [], []
    for start in range(0, n - window + 1, stride):
        end = start + window - 1
        if bad_cum[end + 1] - bad_cum[start] > 0:
            continue
        label = 0
        if fail_date is not None:
            delta = (fail_date - pd.Timestamp(dates[end])).days
            if delta < 1:
                continue
            if delta <= horizon:
                label = 1
        windows.append(feats[start:end + 1])
        labels.append(label)
    return windows, labels


def window_for_inference(df_drive, feature_cols, window=WINDOW, max_fill=MAX_FILL):
    # The last `window` calendar days of a drive. Returns (window, start, end) or None
    # if the drive has too little history or an unfillable gap in that period.
    dates, feats = fill_drive(df_drive, feature_cols, max_fill)
    if len(feats) < window:
        return None
    w = feats[-window:]
    if np.isnan(w).any():
        return None
    return w, pd.Timestamp(dates[-window]), pd.Timestamp(dates[-1])


def to_log_space(X):
    return np.log1p(np.clip(X, 0, None)).astype(np.float32)