
import pandas as pd
import json

path = "data/processed/st12000nm0008_2026q1q2_clean.csv.gz"

df = pd.read_csv(path, compression="gzip")
df["date"] = pd.to_datetime(df["date"])

feature_cols = [
    "smart_1_raw", "smart_3_raw", "smart_4_raw", "smart_5_raw",
    "smart_7_raw", "smart_9_raw", "smart_10_raw", "smart_12_raw",
    "smart_18_raw", "smart_187_raw", "smart_188_raw", "smart_190_raw",
    "smart_192_raw", "smart_193_raw", "smart_194_raw", "smart_195_raw",
    "smart_197_raw", "smart_199_raw", "smart_200_raw", "smart_240_raw",
    "smart_241_raw", "smart_242_raw"
]

selected = None

for serial, group in df.groupby("serial_number"):
    group = group.sort_values("date")
    group = group.dropna(subset=feature_cols)

    for start in range(len(group) - 13):
        candidate = group.iloc[start:start + 14]

        if (candidate["date"].diff().dropna() == pd.Timedelta(days=1)).all():
            selected = candidate
            selected_serial = serial
            break

    if selected is not None:
        break

if selected is None:
    raise ValueError("No 14 consecutive complete readings found.")

readings = selected[["date"] + feature_cols].copy()
readings["date"] = readings["date"].dt.strftime("%Y-%m-%d")

payload = {"readings": readings.to_dict(orient="records")}

with open("test_payload.json", "w") as f:
    json.dump(payload, f, indent=2)

print("Selected drive:", selected_serial)
print("Date range:", readings.iloc[0]["date"], "to", readings.iloc[-1]["date"])
print("Number of readings:", len(readings))
print("Payload saved to test_payload.json")
