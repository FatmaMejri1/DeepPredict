import json
from pathlib import Path

import torch

from .models import RiskNet, LSTMAE
from .preprocess import window_for_inference, to_log_space


class Predictor:
    # Loads the exported artifacts and scores one drive from its raw SMART history.
    def __init__(self, artifact_dir):
        d = Path(artifact_dir)
        self.cfg = json.loads((d / "config.json").read_text(encoding="utf-8"))
        n = len(self.cfg["feature_cols"]) + 1          # SMART columns + gap_filled
        self.risk = RiskNet(n)
        self.risk.load_state_dict(torch.load(d / "risk_gru.pt", map_location="cpu"))
        self.risk.eval()
        self.ae = LSTMAE(n)
        self.ae.load_state_dict(torch.load(d / "anomaly_lstmae.pt", map_location="cpu"))
        self.ae.eval()

    def risk_level(self, score):
        t = self.cfg["thresholds"]["risk"]
        if score >= t["critical"]:
            return "CRITICAL"
        if score >= t["high"]:
            return "HIGH"
        if score >= t["medium"]:
            return "MEDIUM"
        return "LOW"

    def predict(self, df_drive):
        # df_drive: columns `date` plus the raw smart_*_raw columns, one row per reported day.
        out = window_for_inference(df_drive, self.cfg["feature_cols"],
                                   self.cfg["window"], self.cfg["max_fill"])
        if out is None:
            return None                                  # not enough valid history
        w, start, end = out
        x = torch.from_numpy(to_log_space(w)[None])
        with torch.no_grad():
            risk = float(torch.sigmoid(self.risk(x))[0])
            anomaly = float(self.ae.score(x)[0])
        return {
            "risk_score": risk,
            "risk_level": self.risk_level(risk),
            "horizon_days": self.cfg["horizon_days"],
            "anomaly_score": anomaly,
            "is_anomalous": anomaly >= self.cfg["thresholds"]["anomaly"],
            "window_start": start.isoformat(),
            "window_end": end.isoformat(),
            "model_version": self.cfg["version"],
        }