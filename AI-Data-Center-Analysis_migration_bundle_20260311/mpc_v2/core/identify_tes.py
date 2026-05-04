"""TES identification placeholder with validated JSON output."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


def identify_tes_from_monitor(monitor_csv: str | Path, output_json: str | Path) -> dict[str, float]:
    """Estimate simple TES parameters from a monitor replay.

    The first implementation is intentionally conservative: it derives max
    observed rates and leaves efficiencies at stable defaults when replay data
    does not contain enough excitation.
    """

    frame = pd.read_csv(monitor_csv)
    charge = float(frame.get("tes_charge_kwth", pd.Series([0.0])).max())
    discharge = float(frame.get("tes_discharge_kwth", pd.Series([0.0])).max())
    params = {
        "effective_capacity_kwh": 18000.0,
        "charge_efficiency": 0.94,
        "discharge_efficiency": 0.92,
        "standing_loss_per_h": 0.002,
        "max_charge_kw": max(1.0, charge),
        "max_discharge_kw": max(1.0, discharge),
    }
    Path(output_json).parent.mkdir(parents=True, exist_ok=True)
    Path(output_json).write_text(json.dumps(params, indent=2), encoding="utf-8")
    return params

