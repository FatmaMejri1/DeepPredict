
import json
import pandas as pd

from pathlib import Path
from dp_ml.validation import validate_dataset


# 1. Load the trained model configuration.
config_path = Path("models/config.json")

with open(config_path, "r", encoding="utf-8") as f:
    config = json.load(f)


# 2. Load the existing real-data test payload.
with open("test_payload.json", "r", encoding="utf-8") as f:
    payload = json.load(f)

df = pd.DataFrame(payload["readings"])


# 3. Add the expected drive model if metadata is absent.
# This simulates a company providing its drive model information.
if "model" not in df.columns:
    df["model"] = config["drive_model"]


# 4. Run the validation engine.
report = validate_dataset(
    df=df,
    feature_cols=config["feature_cols"],
    expected_drive_model=config["drive_model"],
    window=config["window"],
    max_fill=config["max_fill"],
)


# 5. Display the report.
print("\n========== DEEPPREDICT VALIDATION REPORT ==========\n")

print(json.dumps(report, indent=2))

print("\n===================================================")
print("Validation status:", report["status"])
print("Ready for prediction:", report["ready_for_prediction"])
