
import pandas as pd

from .compatibility import normalize_columns


def validate_dataset(
    df: pd.DataFrame,
    feature_cols: list[str],
    expected_drive_model: str,
    window: int = 14,
    max_fill: int = 3,
    column_mapping: dict[str, str] | None = None,
) -> dict:
    """
    Validate company data before AI prediction.

    This function does not execute the AI models.
    It returns a structured validation report.
    """

    checks = []
    recommendations = []
    errors = []
    warnings = []

    metrics = {
        "total_readings": len(df),
        "available_features": 0,
        "missing_features": [],
        "invalid_dates": 0,
        "duplicate_dates": 0,
        "missing_values": {},
        "invalid_numeric_values": {},
        "negative_values": {},
        "date_range": None,
        "calendar_days": 0,
        "missing_days": 0,
        "max_consecutive_gap": 0,
        "drive_model": None,
    }

    def add_check(name, status, message, details=None):
        check = {
            "name": name,
            "status": status,
            "message": message,
        }

        if details is not None:
            check["details"] = details

        checks.append(check)

        if status == "error":
            errors.append(message)
        elif status == "warning":
            warnings.append(message)

    # 1. Validate input.
    if df.empty:
        add_check(
            "input",
            "error",
            "The uploaded dataset contains no readings."
        )

        return build_report(
            checks, errors, warnings,
            metrics, recommendations
        )

    # 2. Normalize company column names.
    try:
        df = normalize_columns(
            df=df,
            feature_cols=feature_cols,
            column_mapping=column_mapping,
            require_all_features=False,
        )

        add_check(
            "column_compatibility",
            "passed",
            "Column names were successfully normalized."
        )

    except ValueError as exc:
        add_check(
            "column_compatibility",
            "error",
            str(exc)
        )

        recommendations.append(
            "Check the date column and company column mapping."
        )

        return build_report(
            checks, errors, warnings,
            metrics, recommendations
        )

    # 3. Check required SMART features.
    missing = [
        col for col in feature_cols
        if col not in df.columns
    ]

    available = [
        col for col in feature_cols
        if col in df.columns
    ]

    metrics["available_features"] = len(available)
    metrics["missing_features"] = missing

    if missing:
        add_check(
            "required_features",
            "error",
            "Some required SMART features are missing.",
            {
                "missing": missing,
                "available_count": len(available),
                "required_count": len(feature_cols),
            },
        )

        recommendations.append(
            "Provide all missing SMART features or configure "
            "an explicit column mapping."
        )
    else:
        add_check(
            "required_features",
            "passed",
            "All required SMART features are present.",
        )

    # 4. Validate drive model compatibility.
    model_column = None

    if "model" in df.columns:
        model_column = "model"
    elif "drive_model" in df.columns:
        model_column = "drive_model"

    model_compatible = None

    if model_column is None:
        add_check(
            "drive_model",
            "warning",
            "Drive model was not provided. Compatibility cannot be verified."
        )

        recommendations.append(
            f"Provide the drive model. The current AI model "
            f"was trained on {expected_drive_model}."
        )

    else:
        models = (
            df[model_column]
            .dropna()
            .astype(str)
            .str.strip()
            .unique()
            .tolist()
        )

        metrics["drive_model"] = models

        if len(models) == 0:
            add_check(
                "drive_model",
                "warning",
                "No drive model information was found."
            )

            recommendations.append(
                "Provide a valid drive model identifier."
            )

        elif len(models) > 1:
            add_check(
                "drive_model",
                "error",
                "Multiple drive models were found in one dataset.",
                {"detected_models": models},
            )

            recommendations.append(
                "Separate the readings by drive model before validation."
            )

        elif models[0] != expected_drive_model:
            model_compatible = False

            add_check(
                "drive_model",
                "error",
                "The detected drive model is not supported by the current AI model.",
                {
                    "detected_model": models[0],
                    "supported_model": expected_drive_model,
                },
            )

            recommendations.append(
                f"Use a validated model for {models[0]}, "
                f"or provide data from {expected_drive_model}."
            )

        else:
            model_compatible = True

            add_check(
                "drive_model",
                "passed",
                "The drive model matches the trained AI model.",
                {"model": models[0]},
            )

    # 5. Validate dates.
    parsed_dates = pd.to_datetime(
        df["date"],
        errors="coerce"
    )

    invalid_dates = int(parsed_dates.isna().sum())
    metrics["invalid_dates"] = invalid_dates

    if invalid_dates:
        add_check(
            "date_format",
            "error",
            f"{invalid_dates} invalid date values were found."
        )

        recommendations.append(
            "Correct or remove readings with invalid dates."
        )

    valid_mask = parsed_dates.notna()
    valid_df = df.loc[valid_mask].copy()

    valid_df["date"] = (
        parsed_dates.loc[valid_mask].dt.normalize()
    )

    if valid_df.empty:
        add_check(
            "date_coverage",
            "error",
            "No valid dates are available for analysis."
        )

        return build_report(
            checks, errors, warnings,
            metrics, recommendations
        )

    # Check chronological ordering.
    original_dates = parsed_dates.loc[valid_mask]

    if not original_dates.is_monotonic_increasing:
        add_check(
            "date_order",
            "warning",
            "Readings are not chronologically ordered."
        )

        recommendations.append(
            "Sort readings by date before processing."
        )
    else:
        add_check(
            "date_order",
            "passed",
            "Readings are chronologically ordered."
        )

    # Check duplicate calendar days.
    duplicate_count = int(
        valid_df["date"].duplicated().sum()
    )

    metrics["duplicate_dates"] = duplicate_count

    if duplicate_count:
        add_check(
            "duplicate_dates",
            "error",
            f"{duplicate_count} duplicate daily readings were found."
        )

        recommendations.append(
            "Keep one reading per drive per day."
        )
    else:
        add_check(
            "duplicate_dates",
            "passed",
            "No duplicate daily readings were found."
        )

    valid_df = (
        valid_df
        .sort_values("date")
        .drop_duplicates("date", keep="last")
    )

    start_date = valid_df["date"].min()
    end_date = valid_df["date"].max()

    metrics["date_range"] = {
        "start": start_date.isoformat(),
        "end": end_date.isoformat(),
    }

    # 6. Validate SMART values.
    numeric_df = valid_df.copy()

    for feature in available:
        original = numeric_df[feature]

        numeric = pd.to_numeric(
            original,
            errors="coerce"
        )

        invalid_numeric = int(
            (original.notna() & numeric.isna()).sum()
        )

        missing_values = int(numeric.isna().sum())

        negative_values = int(
            (numeric < 0).sum()
        )

        metrics["missing_values"][feature] = missing_values
        metrics["invalid_numeric_values"][feature] = invalid_numeric
        metrics["negative_values"][feature] = negative_values

        numeric_df[feature] = numeric

    total_invalid = sum(
        metrics["invalid_numeric_values"].values()
    )

    total_missing = sum(
        metrics["missing_values"].values()
    )

    total_negative = sum(
        metrics["negative_values"].values()
    )

    if total_invalid:
        add_check(
            "numeric_values",
            "error",
            f"{total_invalid} non-numeric SMART values were found."
        )

        recommendations.append(
            "Convert SMART measurements into valid numeric values."
        )
    else:
        add_check(
            "numeric_values",
            "passed",
            "All provided SMART values are numeric."
        )

    if total_negative:
        add_check(
            "negative_values",
            "error",
            f"{total_negative} negative SMART values were found."
        )

        recommendations.append(
            "Review negative SMART values. Raw SMART counters "
            "should be non-negative."
        )
    else:
        add_check(
            "negative_values",
            "passed",
            "No negative SMART values were found."
        )

    if total_missing:
        add_check(
            "missing_values",
            "warning",
            f"{total_missing} missing SMART values were found.",
            metrics["missing_values"],
        )

        recommendations.append(
            "Review missing SMART measurements. Only limited "
            "forward filling is supported."
        )
    else:
        add_check(
            "missing_values",
            "passed",
            "No missing SMART values were found."
        )

    # 7. Analyze historical coverage and daily gaps.
    full_dates = pd.date_range(
        start=start_date,
        end=end_date,
        freq="D",
    )

    calendar_days = len(full_dates)

    metrics["calendar_days"] = calendar_days
    metrics["missing_days"] = (
        calendar_days - valid_df["date"].nunique()
    )

    observed = full_dates.isin(valid_df["date"])

    # Calculate maximum consecutive missing days.
    max_gap = 0
    current_gap = 0

    for is_observed in observed:
        if is_observed:
            current_gap = 0
        else:
            current_gap += 1
            max_gap = max(max_gap, current_gap)

    metrics["max_consecutive_gap"] = max_gap

    if metrics["missing_days"]:
        add_check(
            "date_gaps",
            "warning",
            f"{metrics['missing_days']} calendar days have no readings.",
            {"max_consecutive_gap": max_gap},
        )
    else:
        add_check(
            "date_gaps",
            "passed",
            "No missing calendar days were found."
        )

    # 8. Check whether a valid inference window exists.
    history_valid = False

    if missing:
        add_check(
            "historical_coverage",
            "warning",
            "History coverage cannot be fully evaluated "
            "because required SMART features are missing."
        )

    elif calendar_days < window:
        add_check(
            "historical_coverage",
            "error",
            f"Insufficient history: {calendar_days} calendar days "
            f"available, but {window} are required."
        )

        recommendations.append(
            f"Provide at least {window} days of valid SMART history."
        )

    else:
        indexed = numeric_df.set_index("date")

        daily = indexed[feature_cols].reindex(full_dates)

        filled = daily.ffill(limit=max_fill)

        last_window = filled.tail(window)

        history_valid = (
            len(last_window) == window
            and not last_window.isna().any().any()
        )

        if history_valid:
            add_check(
                "historical_coverage",
                "passed",
                f"At least {window} consecutive daily positions "
                "are available after permitted forward filling."
            )
        else:
            add_check(
                "historical_coverage",
                "error",
                f"No valid {window}-day inference window is available "
                f"with a maximum forward fill of {max_fill} days."
            )

            recommendations.append(
                "Provide additional SMART readings or reduce "
                "the gaps in the historical data."
            )

    return build_report(
        checks,
        errors,
        warnings,
        metrics,
        recommendations,
        model_compatible=model_compatible,
        history_valid=history_valid,
    )


def build_report(
    checks,
    errors,
    warnings,
    metrics,
    recommendations,
    model_compatible=None,
    history_valid=False,
):
    """Build the final structured validation report."""

    if errors:
        status = "invalid"
    elif warnings:
        status = "warning"
    else:
        status = "valid"

    return {
        "status": status,
        "ready_for_prediction": len(errors) == 0,
        "model_compatibility_verified": model_compatible,
        "history_valid": history_valid,
        "summary": {
            "total_checks": len(checks),
            "passed": sum(
                check["status"] == "passed"
                for check in checks
            ),
            "warnings": len(warnings),
            "errors": len(errors),
        },
        "metrics": metrics,
        "checks": checks,
        "errors": errors,
        "warnings": warnings,
        "recommendations": list(dict.fromkeys(recommendations)),
    }
