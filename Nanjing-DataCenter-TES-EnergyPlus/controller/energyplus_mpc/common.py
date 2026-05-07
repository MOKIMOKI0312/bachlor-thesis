"""Shared helpers for EnergyPlus-MPC coupling."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml


REPO_ROOT = Path(__file__).resolve().parents[3]
EPLUS_ROOT = REPO_ROOT / "Nanjing-DataCenter-TES-EnergyPlus"
DEFAULT_EPLUS_INSTALL = Path(
    "C:/Users/18430/EnergyPlus-23.1.0/EnergyPlus-23.1.0-87ed9199d4-Windows-x86_64"
)
DEFAULT_MODEL = EPLUS_ROOT / "model" / "Nanjing_DataCenter_TES.epJSON"
DEFAULT_WEATHER = EPLUS_ROOT / "weather" / "CHN_JS_Nanjing.582380_TMYx.2009-2023.epw"
DEFAULT_PRICE = EPLUS_ROOT / "inputs" / "Jiangsu_TOU_2025_hourly.csv"
DEFAULT_PV = EPLUS_ROOT / "inputs" / "CHN_Nanjing_PV_6MWp_hourly.csv"
DEFAULT_BASELINE_TIMESERIES = EPLUS_ROOT / "out" / "energyplus_nanjing" / "timeseries_15min.csv"
DEFAULT_PARAM_YAML = EPLUS_ROOT / "controller" / "energyplus_mpc" / "config" / "energyplus_mpc_params.yaml"
DEFAULT_SELECTED_ROOT = REPO_ROOT / "results" / "energyplus_mpc_20260507"


@dataclass(frozen=True)
class ExternalSeries:
    price_per_kwh: pd.Series
    pv_kw: pd.Series


def read_yaml(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"YAML must contain a mapping: {path}")
    return data


def write_yaml(path: str | Path, data: dict[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(data, fh, sort_keys=False, allow_unicode=True)


def load_external_series(price_csv: str | Path = DEFAULT_PRICE, pv_csv: str | Path = DEFAULT_PV) -> ExternalSeries:
    price_frame = pd.read_csv(price_csv)
    pv_frame = pd.read_csv(pv_csv)
    price_col = [c for c in price_frame.columns if c != "timestamp"][0]
    pv_col = [c for c in pv_frame.columns if c != "timestamp"][0]
    price = pd.Series(
        pd.to_numeric(price_frame[price_col], errors="raise").astype(float).to_numpy(),
        index=pd.to_datetime(price_frame["timestamp"]),
    ).sort_index()
    if "mwh" in price_col.lower():
        price = price / 1000.0
    pv = pd.Series(
        pd.to_numeric(pv_frame[pv_col], errors="raise").astype(float).to_numpy(),
        index=pd.to_datetime(pv_frame["timestamp"]),
    ).sort_index()
    return ExternalSeries(price_per_kwh=price, pv_kw=pv)


def cyclic_lookup(series: pd.Series, timestamps: list[datetime]) -> np.ndarray:
    by_key = {(ts.month, ts.day, ts.hour, ts.minute): float(value) for ts, value in series.items()}
    fallback = float(series.iloc[0])
    return np.asarray([by_key.get((ts.month, ts.day, ts.hour, ts.minute), fallback) for ts in timestamps], dtype=float)


def load_baseline_timeseries(path: str | Path = DEFAULT_BASELINE_TIMESERIES) -> pd.DataFrame:
    frame = pd.read_csv(path)
    frame["timestamp"] = pd.to_datetime(frame["timestamp"])
    frame["interval_start"] = pd.to_datetime(frame["interval_start"])
    return frame


def tes_set_from_q_tes_net(q_tes_net_kw_th: float, q_abs_max_kw_th: float) -> float:
    """Map Kim-lite signed net TES action to EnergyPlus TES_Set schedule value."""

    if q_abs_max_kw_th <= 0:
        raise ValueError("q_abs_max_kw_th must be positive")
    return float(-np.clip(q_tes_net_kw_th / q_abs_max_kw_th, -1.0, 1.0))


def ensure_path(path: str | Path, label: str, file: bool = True) -> Path:
    target = Path(path)
    if file and not target.is_file():
        raise FileNotFoundError(f"{label} not found: {target}")
    if not file and not target.is_dir():
        raise FileNotFoundError(f"{label} not found: {target}")
    return target
