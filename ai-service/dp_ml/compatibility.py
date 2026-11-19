
import re
import pandas as pd


# Common aliases for fields used by the trained models.
# Add an alias only when its meaning is equivalent to the SMART attribute.
SMART_ALIASES = {
    "smart_5_raw": [
        "smart_5",
        "smart5",
        "reallocated_sector_count",
        "reallocated_sectors",
    ],
    "smart_187_raw": [
        "smart_187",
        "smart187",
        "reported_uncorrectable_errors",
    ],
    "smart_197_raw": [
        "smart_197",
        "smart197",
        "current_pending_sector_count",
        "pending_sectors",
    ],
    "smart_198_raw": [
        "smart_198",
        "smart198",
        "offline_uncorrectable_sector_count",
    ],
    "smart_194_raw": [
        "smart_194",
        "smart194",
        "temperature",
        "temperature_celsius",
    ],
    "smart_9_raw": [
        "smart_9",
        "smart9",
        "power_on_hours",
    ],
    "smart_12_raw": [
        "smart_12",
        "smart12",
        "power_cycle_count",
    ],
}


DATE_ALIASES = [
    "timestamp",
    "datetime",
    "date_time",
    "reading_date",
    "measurement_date",
]


def normalize_name(name: str) -> str:
    """Normalize a column name for comparison."""
    return re.sub(r"[^a-z0-9]", "", str(name).lower())


def normalize_columns(
    df: pd.DataFrame,
    feature_cols: list[str],
    column_mapping: dict[str, str] | None = None,
    require_all_features: bool = True,
) -> pd.DataFrame:
    """
    Convert company column names into the canonical names
    expected by the trained DeepPredict models.

    column_mapping direction:
        company_column -> DeepPredict_column
    """

    df = df.copy()

    # 1. Normalize the date column using common aliases.
    date_candidates = ["date"] + DATE_ALIASES

    date_lookup = {
        normalize_name(col): col for col in df.columns
    }

    if "date" not in df.columns:
        for candidate in date_candidates:
            source = date_lookup.get(normalize_name(candidate))

            if source is not None:
                df = df.rename(columns={source: "date"})
                break

    # 2. Apply explicit mapping supplied by the company.
    if column_mapping:
        for company_col, canonical_col in column_mapping.items():

            if company_col not in df.columns:
                raise ValueError(
                    f"Mapped company column '{company_col}' does not exist."
                )

            if canonical_col != "date" and canonical_col not in feature_cols:
                raise ValueError(
                    f"'{canonical_col}' is not a supported model feature."
                )

            if company_col != canonical_col:
                if canonical_col in df.columns:
                    raise ValueError(
                        f"Cannot map '{company_col}' to '{canonical_col}': "
                        "the target column already exists."
                    )

                df = df.rename(
                    columns={company_col: canonical_col}
                )

    # 3. Check that the date column exists after explicit mapping.
    if "date" not in df.columns:
        raise ValueError(
            "No date column found. Expected date, timestamp or datetime."
        )

    # 4. Build automatic aliases for the model features.
    aliases = {}

    for canonical in feature_cols:
        aliases[normalize_name(canonical)] = canonical

        # Support names such as smart_5, smart5, smart_5_raw.
        match = re.fullmatch(r"smart_(\d+)_raw", canonical)

        if match:
            number = match.group(1)

            aliases[normalize_name(f"smart_{number}")] = canonical
            aliases[normalize_name(f"smart{number}")] = canonical
            aliases[normalize_name(f"smart{number}_raw")] = canonical

        for alias in SMART_ALIASES.get(canonical, []):
            aliases[normalize_name(alias)] = canonical

    # 5. Rename recognized SMART columns.
    rename_map = {}

    for company_col in df.columns:
        normalized = normalize_name(company_col)
        canonical = aliases.get(normalized)

        if canonical and company_col != canonical:

            if canonical in df.columns or canonical in rename_map.values():
                raise ValueError(
                    f"Multiple columns correspond to '{canonical}'. "
                    "Please provide an explicit, unambiguous mapping."
                )

            rename_map[company_col] = canonical

    df = df.rename(columns=rename_map)


    # 6. Check required model features.
    missing = [
        col for col in feature_cols
        if col not in df.columns
    ]

    if missing and require_all_features:
        raise ValueError(
            "Missing required SMART features: " + ", ".join(missing)
        )

    return df
