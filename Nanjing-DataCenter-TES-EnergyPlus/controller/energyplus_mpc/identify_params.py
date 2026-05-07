"""Identify simple MPC proxy parameters from EnergyPlus 15-minute output."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .common import DEFAULT_BASELINE_TIMESERIES, DEFAULT_PARAM_YAML, load_baseline_timeseries, read_yaml, write_yaml
from .extract_params import extract_static_params


def identify_from_timeseries(timeseries_path: str | Path = DEFAULT_BASELINE_TIMESERIES) -> dict[str, Any]:
    frame = load_baseline_timeseries(timeseries_path)
    cooling = frame["chiller_cooling_kw"].clip(lower=0.0).to_numpy(dtype=float)
    power = frame["chiller_electricity_kw"].clip(lower=0.0).to_numpy(dtype=float)
    active = cooling > 100.0
    if active.sum() >= 2:
        a, b = np.polyfit(cooling[active], power[active], deg=1)
    else:
        a, b = 0.126, 90.0
    p_nonplant = frame["facility_electricity_kw"] - frame["chiller_electricity_kw"]
    q_load = frame["chiller_cooling_kw"] + frame["tes_use_side_kw"].clip(lower=0.0) - frame["tes_source_side_kw"].clip(lower=0.0)
    tank_temp = frame["tes_tank_temp_c"].astype(float)
    soc = ((12.0 - tank_temp) / (12.0 - 6.67)).clip(0.0, 1.0)
    no_tes = (frame["tes_use_side_kw"].abs() < 1e-6) & (frame["tes_source_side_kw"].abs() < 1e-6)
    drift = float(soc[no_tes].diff().abs().median()) if no_tes.any() else 0.0
    return {
        "timeseries_path": str(timeseries_path),
        "rows": int(len(frame)),
        "facility_base_kw_median": float(frame["facility_electricity_kw"].median()),
        "p_nonplant_kw_median": float(p_nonplant.median()),
        "q_load_kw_th_median": float(q_load.clip(lower=0.0).median()),
        "q_load_kw_th_p95": float(q_load.clip(lower=0.0).quantile(0.95)),
        "outdoor_wetbulb_c_mean": float(frame["outdoor_wetbulb_c"].mean()),
        "outdoor_wetbulb_c_amp_proxy": float((frame["outdoor_wetbulb_c"].quantile(0.95) - frame["outdoor_wetbulb_c"].quantile(0.05)) / 2.0),
        "chiller_fit": {
            "a_kw_per_kwth": float(a),
            "b_kw": float(b),
            "active_points": int(active.sum()),
        },
        "tes_response": {
            "max_use_side_kw": float(frame["tes_use_side_kw"].max()),
            "max_source_side_kw": float(frame["tes_source_side_kw"].max()),
            "soc_initial_from_tank_temp": float(soc.iloc[0]),
            "soc_no_tes_abs_drift_median_per_step": drift,
        },
    }


def merge_identified(params: dict[str, Any], identified: dict[str, Any]) -> dict[str, Any]:
    merged = dict(params)
    merged["identified"] = identified
    tes = dict(merged["tes"])
    q_abs = max(identified["tes_response"]["max_use_side_kw"], identified["tes_response"]["max_source_side_kw"], 4500.0)
    tes["q_abs_max_kw_th_proxy"] = float(q_abs)
    tes["initial_soc_from_baseline"] = float(identified["tes_response"]["soc_initial_from_tank_temp"])
    merged["tes"] = tes
    merged["plant_proxy"] = {
        "q_load_kw_th": float(identified["q_load_kw_th_median"]),
        "p_nonplant_kw": float(identified["p_nonplant_kw_median"]),
        "wet_bulb_base_c": float(identified["outdoor_wetbulb_c_mean"]),
        "wet_bulb_amp_c": float(identified["outdoor_wetbulb_c_amp_proxy"]),
        "modes": [
            {
                "q_min_kw_th": 0.0,
                "q_max_kw_th": max(float(identified["q_load_kw_th_p95"]) * 1.5, 8000.0),
                "a_kw_per_kwth": float(identified["chiller_fit"]["a_kw_per_kwth"]),
                "b_kw": max(float(identified["chiller_fit"]["b_kw"]), 0.0),
                "c_kw_per_c": 0.0,
            }
        ],
    }
    return merged


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeseries", default=str(DEFAULT_BASELINE_TIMESERIES))
    parser.add_argument("--params", default=str(DEFAULT_PARAM_YAML))
    parser.add_argument("--output", default=str(DEFAULT_PARAM_YAML))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    params_path = Path(args.params)
    params = read_yaml(params_path) if params_path.exists() else extract_static_params()
    identified = identify_from_timeseries(args.timeseries)
    write_yaml(args.output, merge_identified(params, identified))
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
