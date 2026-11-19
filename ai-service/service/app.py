
import torch  # noqa: F401 (must come first on Windows)
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from dp_ml.inference import Predictor
from dp_ml.compatibility import normalize_columns
from dp_ml.validation import validate_dataset


ARTIFACTS = Path(__file__).resolve().parents[1] / "models"
predictor = Predictor(ARTIFACTS)

app = FastAPI(title="DeepPredict AI service")


class PredictRequest(BaseModel):
    readings: list[dict]
    column_mapping: dict[str, str] | None = None


@app.get("/health")
def health():
    return {
        "status": "ok",
        "model_version": predictor.cfg["version"]
    }


@app.post("/validate")
def validate(req: PredictRequest):

    if not req.readings:
        raise HTTPException(422, "readings is empty")

    df = pd.DataFrame(req.readings)

    try:
        report = validate_dataset(
            df=df,
            feature_cols=predictor.cfg["feature_cols"],
            expected_drive_model=predictor.cfg["drive_model"],
            window=predictor.cfg["window"],
            max_fill=predictor.cfg["max_fill"],
            column_mapping=req.column_mapping,
        )

        return report

    except ValueError as e:
        raise HTTPException(422, str(e))


@app.post("/predict")
def predict(req: PredictRequest):

    if not req.readings:
        raise HTTPException(422, "readings is empty")

    df = pd.DataFrame(req.readings)

    try:
        # 1. Validate the submitted dataset.
        report = validate_dataset(
            df=df,
            feature_cols=predictor.cfg["feature_cols"],
            expected_drive_model=predictor.cfg["drive_model"],
            window=predictor.cfg["window"],
            max_fill=predictor.cfg["max_fill"],
            column_mapping=req.column_mapping,
        )

        # 2. Reject invalid or unverified drive compatibility.
        if (
            not report["ready_for_prediction"]
            or not report["history_valid"]
            or report["model_compatibility_verified"] is not True
        ):
            raise HTTPException(
                status_code=422,
                detail={
                    "message": (
                        "Dataset validation failed or drive model "
                        "compatibility could not be verified. "
                        "Prediction was not performed."
                    ),
                    "validation_report": report,
                },
            )

        # 3. Normalize company column names.
        df = normalize_columns(
            df=df,
            feature_cols=predictor.cfg["feature_cols"],
            column_mapping=req.column_mapping,
        )

        # 4. Convert date values.
        df["date"] = pd.to_datetime(df["date"], errors="coerce")

        if df["date"].isna().any():
            raise ValueError("Some date values are invalid.")

        # 5. Run the existing trained AI models.
        out = predictor.predict(df)

        if out is None:
            raise HTTPException(
                status_code=422,
                detail=(
                    "Not enough valid history: need 14 days "
                    "with gaps of up to 3 days filled."
                ),
            )

        return out

    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
