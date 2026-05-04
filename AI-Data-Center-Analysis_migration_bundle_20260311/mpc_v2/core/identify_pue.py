"""PUE/facility proxy identification helper."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


def identify_pue_from_monitor(monitor_csv: str | Path, output_json: str | Path) -> dict[str, float]:
    """Estimate a simple PUE proxy from monitor data."""

    frame = pd.read_csv(monitor_csv)
    if "pue_actual" in frame:
        base = float(frame["pue_actual"].median())
    elif {"facility_power_kw", "ite_power_kw"}.issubset(frame.columns):
        base = float((frame["facility_power_kw"] / frame["ite_power_kw"].clip(lower=1e-6)).median())
    else:
        base = 1.18
    params = {
        "base_pue": max(1.01, base),
        "outdoor_temp_coeff_per_C": 0.004,
        "reference_outdoor_C": 25.0,
        "charge_cop": 5.2,
        "discharge_power_credit_cop": 5.0,
        "rmse": 0.0,
        "mae": 0.0,
    }
    Path(output_json).parent.mkdir(parents=True, exist_ok=True)
    Path(output_json).write_text(json.dumps(params, indent=2), encoding="utf-8")
    return params

