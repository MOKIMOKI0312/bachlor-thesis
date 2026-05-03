"""Offline audit for M2-F1 TES TOU reward shaping candidates.

The audit compares existing learned/rule/neutral monitor.csv traces against a
candidate non-PBRS TOU action-alignment term:

    r = weight * desired_sign * tes_valve_target

where desired_sign is +1 for high-price discharge, -1 for low-price charge
before an upcoming peak, and 0 otherwise.  This script does not run EnergyPlus
or train a policy.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


REWARD_AUDIT_FIELDS = [
    "reward",
    "cost_term",
    "energy_term",
    "comfort_term",
    "tes_pbrs_term",
    "tes_teacher_term",
    "tes_tou_alignment_term",
    "tes_valve_penalty",
    "tes_invalid_action_penalty",
    "tes_shaping_total",
]
BASE_REWARD_FIELDS = ["reward", "cost_term", "energy_term", "comfort_term"]
KEY_TES_REWARD_FIELDS = [
    "tes_pbrs_term",
    "tes_teacher_term",
    "tes_tou_alignment_term",
    "tes_valve_penalty",
    "tes_invalid_action_penalty",
]
REQUIRED_REWARD_FIELDS = [*BASE_REWARD_FIELDS, *KEY_TES_REWARD_FIELDS]
WINDOW_SIGNAL_FIELDS = [
    "TES_SOC",
    "tes_valve_target",
    "raw_tes_action",
    "TES_valve_wrapper_position",
    "price_current_norm",
    "price_hours_to_next_peak_norm",
]
SHAPING_COMPONENT_FIELDS = [
    "tes_pbrs_term",
    "tes_teacher_term",
    "tes_tou_alignment_term",
    "tes_valve_penalty",
    "tes_invalid_action_penalty",
]
RAW_TES_ACTION_COLUMNS = ["tes_valve_target", "TES_DRL"]
ACTUAL_VALVE_COLUMNS = ["TES_valve_wrapper_position", "tes_valve_position"]


def numeric(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        raise KeyError(f"Missing required monitor column: {column}")
    return pd.to_numeric(df[column], errors="coerce").astype(float)


def optional_numeric(df: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    if column not in df.columns:
        return pd.Series(default, index=df.index, dtype=float)
    return pd.to_numeric(df[column], errors="coerce").fillna(default).astype(float)


def nullable_numeric(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        return pd.Series(np.nan, index=df.index, dtype=float)
    return pd.to_numeric(df[column], errors="coerce").astype(float)


def first_present_column(df: pd.DataFrame, columns: list[str]) -> str | None:
    for column in columns:
        if column in df.columns:
            return column
    return None


def nullable_cell(series: pd.Series, idx: int) -> float | None:
    if idx < 0 or idx >= len(series):
        return None
    value = series.iloc[idx]
    if pd.isna(value):
        return None
    out = float(value)
    return out if math.isfinite(out) else None


def json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): json_ready(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_ready(v) for v in value]
    if isinstance(value, tuple):
        return [json_ready(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value) if math.isfinite(float(value)) else None
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    return value


def pre_action_signal(series: pd.Series) -> pd.Series:
    shifted = series.shift(1)
    if len(shifted):
        shifted.iloc[0] = series.iloc[0]
    return shifted.astype(float)


def bool_fraction(series: pd.Series) -> float:
    truthy = {"1", "true", "True", "TRUE", "yes", "Yes", "YES"}
    return float(series.astype(str).isin(truthy).mean()) if len(series) else 0.0


def choose_target_column(df: pd.DataFrame) -> str:
    for column in ("tes_valve_target", "TES_DRL", "TES_valve_wrapper_position"):
        if column in df.columns:
            return column
    raise KeyError(
        "Monitor must contain one of: tes_valve_target, TES_DRL, "
        "TES_valve_wrapper_position"
    )


def desired_sign(
    soc: pd.Series,
    price: pd.Series,
    hours_to_peak: pd.Series,
    args: argparse.Namespace,
) -> pd.Series:
    desired = pd.Series(0.0, index=soc.index, dtype=float)
    high = (price >= args.high_price_threshold) & (soc > args.soc_discharge_limit)
    low = (
        (price <= args.low_price_threshold)
        & (hours_to_peak <= args.near_peak_threshold)
        & (soc < args.soc_charge_limit)
    )
    desired.loc[high] = 1.0
    desired.loc[low] = -1.0
    return desired


def mean_or_none(series: pd.Series) -> float | None:
    if len(series) == 0:
        return None
    value = float(series.dropna().mean()) if len(series.dropna()) else float("nan")
    return value if np.isfinite(value) else None


def contiguous_true_runs(mask: pd.Series) -> list[tuple[int, int]]:
    arr = mask.fillna(False).to_numpy(dtype=bool)
    runs: list[tuple[int, int]] = []
    start: int | None = None
    for idx, flag in enumerate(arr):
        if flag and start is None:
            start = idx
        elif not flag and start is not None:
            runs.append((start, idx))
            start = None
    if start is not None:
        runs.append((start, len(arr)))
    return runs


def series_for_term(df: pd.DataFrame, term: str) -> pd.Series:
    if term == "tes_shaping_total" and term not in df.columns:
        components = [nullable_numeric(df, col) for col in SHAPING_COMPONENT_FIELDS if col in df.columns]
        if not components:
            return pd.Series(np.nan, index=df.index, dtype=float)
        stacked = pd.concat(components, axis=1)
        return stacked.sum(axis=1, min_count=1)
    return nullable_numeric(df, term)


def reward_audit_field_status(df: pd.DataFrame) -> dict[str, Any]:
    available = [field for field in REQUIRED_REWARD_FIELDS if field in df.columns]
    missing = [field for field in REQUIRED_REWARD_FIELDS if field not in df.columns]
    missing_base = [field for field in BASE_REWARD_FIELDS if field not in df.columns]
    missing_tes = [field for field in KEY_TES_REWARD_FIELDS if field not in df.columns]

    if not missing:
        status = "complete"
        limitation = (
            "All configured reward audit fields are present; this artifact can be used "
            "to inspect PBRS, teacher, TOU alignment, valve penalty, and invalid-action "
            "penalty contributions around TOU windows."
        )
    elif missing_base:
        status = "missing_required_fields"
        limitation = (
            f"Missing base reward decomposition fields {missing_base}. This artifact is "
            "limited to available signals and cannot support reward decomposition conclusions."
        )
    else:
        status = "partial"
        limitation = (
            f"Missing TES reward decomposition fields {missing_tes}. This artifact cannot "
            "determine whether PBRS, teacher/alignment shaping, valve penalty, or invalid-action "
            "penalty suppressed low-price charging; nulls in those columns mean missing evidence, not zero."
        )

    return {
        "reward_audit_status": status,
        "missing_reward_fields": missing,
        "available_reward_fields": available,
        "audit_limitation": limitation,
    }


def row_value(series_by_name: dict[str, pd.Series], name: str, idx: int) -> float | None:
    return nullable_cell(series_by_name[name], idx) if name in series_by_name else None


def mean_for_mask(series: pd.Series, mask: pd.Series) -> float | None:
    return mean_or_none(series.loc[mask.fillna(False)])


def soc_delta_for_run(soc: pd.Series, start: int, end: int) -> float | None:
    if end <= start:
        return None
    first = nullable_cell(soc, start)
    last = nullable_cell(soc, end - 1)
    if first is None or last is None:
        return None
    return float(last - first)


def window_masks(df: pd.DataFrame, args: argparse.Namespace) -> tuple[pd.Series, pd.Series, list[str]]:
    notes: list[str] = []
    required = ["TES_SOC", "price_current_norm"]
    missing = [column for column in required if column not in df.columns]
    if missing:
        notes.append(f"missing required window columns: {missing}")
        false_mask = pd.Series(False, index=df.index, dtype=bool)
        return false_mask, false_mask, notes

    soc = pre_action_signal(nullable_numeric(df, "TES_SOC").clip(0.0, 1.0))
    price = pre_action_signal(nullable_numeric(df, "price_current_norm"))
    if "price_hours_to_next_peak_norm" in df.columns:
        hours_to_peak = pre_action_signal(nullable_numeric(df, "price_hours_to_next_peak_norm"))
    else:
        hours_to_peak = pd.Series(np.nan, index=df.index, dtype=float)
        notes.append("missing price_hours_to_next_peak_norm; low-price charge windows unavailable")

    low_charge = (
        price.notna()
        & hours_to_peak.notna()
        & soc.notna()
        & (price <= args.low_price_threshold)
        & (hours_to_peak <= args.near_peak_threshold)
        & (soc < args.soc_charge_limit)
    )
    high_discharge = (
        price.notna()
        & soc.notna()
        & (price >= args.high_price_threshold)
        & (soc > args.soc_discharge_limit)
    )
    return low_charge, high_discharge, notes


def window_type_label(window_type: str) -> str:
    if window_type == "low_price_charge":
        return "low_price_charge_prepeak"
    if window_type == "high_price_discharge":
        return "peak_price_discharge"
    return window_type


def build_window_audit_for_monitor(path: Path, monitor_index: int, args: argparse.Namespace) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if not path.exists():
        summary = {
            "monitor_csv": str(path),
            "status": "missing_monitor_csv",
            "reason": f"Monitor CSV not found: {path}",
            "window_summaries": [],
            "windows": [],
        }
        return summary, []

    df = pd.read_csv(path, index_col=False)
    audit_status = reward_audit_field_status(df)
    raw_col = first_present_column(df, RAW_TES_ACTION_COLUMNS)
    actual_col = first_present_column(df, ACTUAL_VALVE_COLUMNS)
    low_mask, high_mask, notes = window_masks(df, args)
    term_series = {term: series_for_term(df, term) for term in REWARD_AUDIT_FIELDS}
    soc = nullable_numeric(df, "TES_SOC")
    raw = nullable_numeric(df, raw_col) if raw_col else pd.Series(np.nan, index=df.index, dtype=float)
    actual = nullable_numeric(df, actual_col) if actual_col else pd.Series(np.nan, index=df.index, dtype=float)
    price = nullable_numeric(df, "price_current_norm")
    hours_to_peak = nullable_numeric(df, "price_hours_to_next_peak_norm")
    timestep = nullable_numeric(df, "timestep")
    if raw_col is None:
        notes.append("missing raw TES action column; raw/target valve fields are null")
    if actual_col is None:
        notes.append("missing actual valve column; actual valve fields are null")

    rows: list[dict[str, Any]] = []
    windows: list[dict[str, Any]] = []
    window_specs = [
        ("low_price_charge", low_mask),
        ("high_price_discharge", high_mask),
    ]

    for window_type, mask in window_specs:
        for run_index, (start, end) in enumerate(contiguous_true_runs(mask), start=1):
            window_id = f"m{monitor_index}_{window_type}_{run_index}"
            context_start = max(0, start - args.context_steps)
            context_end = min(len(df), start + args.context_steps + 1)
            core_mask = pd.Series(False, index=df.index, dtype=bool)
            core_mask.iloc[start:end] = True
            context_indices = range(context_start, context_end)
            soc_delta = soc_delta_for_run(soc, start, end)
            window_summary = {
                "monitor_csv": str(path),
                **audit_status,
                "window_id": window_id,
                "window_type": window_type_label(window_type),
                "window_start_index": int(start),
                "window_end_exclusive_index": int(end),
                "window_start_timestep": nullable_cell(timestep, start),
                "window_end_timestep": nullable_cell(timestep, end - 1),
                "window_length_steps": int(end - start),
                "context_start_index": int(context_start),
                "context_end_exclusive_index": int(context_end),
                "context_row_count": int(context_end - context_start),
                "raw_tes_action_column": raw_col,
                "actual_valve_column": actual_col,
                "raw_tes_action_mean": mean_for_mask(raw, core_mask),
                "actual_valve_mean": mean_for_mask(actual, core_mask),
                "soc_delta": soc_delta,
            }
            for term in REWARD_AUDIT_FIELDS:
                window_summary[f"{term}_mean"] = mean_for_mask(term_series[term], core_mask)
            windows.append(window_summary)

            for idx in context_indices:
                detail = {
                    "monitor_csv": str(path),
                    **audit_status,
                    "monitor_index": int(monitor_index),
                    "window_id": window_id,
                    "window_type": window_type_label(window_type),
                    "window_start_index": int(start),
                    "window_start_timestep": nullable_cell(timestep, start),
                    "row_index": int(idx),
                    "row_offset_from_window_start": int(idx - start),
                    "timestep": nullable_cell(timestep, idx),
                    "in_core_window": bool(start <= idx < end),
                    "raw_tes_action_column": raw_col,
                    "actual_valve_column": actual_col,
                }
                for term in REWARD_AUDIT_FIELDS:
                    detail[term] = row_value(term_series, term, idx)
                detail["TES_SOC"] = nullable_cell(soc, idx)
                detail["tes_valve_target"] = nullable_cell(raw, idx)
                detail["raw_tes_action"] = nullable_cell(raw, idx)
                detail["TES_valve_wrapper_position"] = nullable_cell(actual, idx)
                detail["price_current_norm"] = nullable_cell(price, idx)
                detail["price_hours_to_next_peak_norm"] = nullable_cell(hours_to_peak, idx)
                rows.append(detail)

    window_summaries: list[dict[str, Any]] = []
    for window_type, mask in window_specs:
        runs = contiguous_true_runs(mask)
        core_mask = mask.fillna(False)
        deltas = [
            delta
            for start, end in runs
            for delta in [soc_delta_for_run(soc, start, end)]
            if delta is not None
        ]
        summary = {
            "monitor_csv": str(path),
            **audit_status,
            "window_type": window_type_label(window_type),
            "window_count": int(len(runs)),
            "window_row_count": int(core_mask.sum()),
            "context_row_count": int(sum(min(len(df), start + args.context_steps + 1) - max(0, start - args.context_steps) for start, _ in runs)),
            "raw_tes_action_column": raw_col,
            "actual_valve_column": actual_col,
            "raw_tes_action_mean": mean_for_mask(raw, core_mask),
            "actual_valve_mean": mean_for_mask(actual, core_mask),
            "soc_delta_mean": float(np.mean(deltas)) if deltas else None,
        }
        for term in REWARD_AUDIT_FIELDS:
            summary[f"{term}_mean"] = mean_for_mask(term_series[term], core_mask)
        window_summaries.append(summary)

    summary = {
        "monitor_csv": str(path),
        "status": "ok",
        **audit_status,
        "rows": int(len(df)),
        "notes": notes,
        "raw_tes_action_column": raw_col,
        "actual_valve_column": actual_col,
        "window_count": int(len(windows)),
        "detail_row_count": int(len(rows)),
        "window_summaries": window_summaries,
        "windows": windows,
    }
    return summary, rows


def write_window_audit_outputs(payload: dict[str, Any], rows: list[dict[str, Any]], args: argparse.Namespace) -> None:
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(json_ready(payload), indent=2), encoding="utf-8")
    if args.csv_out:
        args.csv_out.parent.mkdir(parents=True, exist_ok=True)
        fields = list(
            dict.fromkeys(
                [
                    "monitor_csv",
                    "monitor_index",
                    "reward_audit_status",
                    "missing_reward_fields",
                    "available_reward_fields",
                    "audit_limitation",
                    "window_id",
                    "window_type",
                    "window_start_index",
                    "window_start_timestep",
                    "row_index",
                    "row_offset_from_window_start",
                    "timestep",
                    "in_core_window",
                    *REWARD_AUDIT_FIELDS,
                    *WINDOW_SIGNAL_FIELDS,
                    "raw_tes_action_column",
                    "actual_valve_column",
                ]
                + sorted({key for row in rows for key in row.keys()})
            )
        )
        with args.csv_out.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(json_ready(rows))


def cmd_window_audit(args: argparse.Namespace) -> int:
    all_rows: list[dict[str, Any]] = []
    monitors: list[dict[str, Any]] = []
    for monitor_index, monitor_path in enumerate(args.monitors, start=1):
        summary, rows = build_window_audit_for_monitor(monitor_path, monitor_index, args)
        monitors.append(summary)
        all_rows.extend(rows)

    payload = {
        "title": "M2-F1 TES reward/window audit",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "thresholds": {
            "high_price_threshold": float(args.high_price_threshold),
            "low_price_threshold": float(args.low_price_threshold),
            "near_peak_threshold": float(args.near_peak_threshold),
            "soc_charge_limit": float(args.soc_charge_limit),
            "soc_discharge_limit": float(args.soc_discharge_limit),
            "context_steps": int(args.context_steps),
        },
        "sign_convention": "negative valve = charge, positive valve = discharge",
        "reward_audit_status_counts": dict(
            pd.Series([monitor.get("reward_audit_status", "unknown") for monitor in monitors]).value_counts()
        ),
        "monitors": monitors,
        "detail_rows": all_rows,
    }
    write_window_audit_outputs(payload, all_rows, args)
    print(f"Wrote {args.out}")
    if args.csv_out:
        print(f"Wrote {args.csv_out}")
    print(
        json.dumps(
            json_ready(
                {
                    "monitor_count": len(monitors),
                    "detail_row_count": len(all_rows),
                    "window_count": sum(int(monitor.get("window_count", 0)) for monitor in monitors),
                    "statuses": dict(pd.Series([monitor.get("status", "unknown") for monitor in monitors]).value_counts()),
                }
            ),
            indent=2,
        )
    )
    return 0 if any(monitor.get("status") == "ok" for monitor in monitors) else 1


def summarize_trace(label: str, path: Path, args: argparse.Namespace) -> dict[str, Any]:
    df = pd.read_csv(path)
    target_col = choose_target_column(df)

    price_current = numeric(df, "price_current_norm")
    price = pre_action_signal(price_current)
    soc = pre_action_signal(numeric(df, "TES_SOC").clip(0.0, 1.0))
    hours_to_peak = pre_action_signal(numeric(df, "price_hours_to_next_peak_norm"))
    target = optional_numeric(df, target_col).clip(-1.0, 1.0)
    actual = optional_numeric(df, "TES_valve_wrapper_position").clip(-1.0, 1.0)
    temp = optional_numeric(df, "air_temperature", default=np.nan)

    desired = desired_sign(soc, price, hours_to_peak, args)
    alignment = args.weight * desired * target

    high_price = price_current >= price_current.quantile(0.75)
    low_price = price_current <= price_current.quantile(0.25)
    low_discharge = (desired < 0.0) & (target > args.active_threshold)
    high_discharge = (desired > 0.0) & (target > args.active_threshold)
    low_charge = (desired < 0.0) & (target < -args.active_threshold)
    high_charge = (desired > 0.0) & (target < -args.active_threshold)
    comfort_violation = temp > args.comfort_high

    comfort_term = optional_numeric(df, "comfort_term", default=0.0)
    comfort_alignment_net = comfort_term + alignment
    comfort_rows = alignment.loc[comfort_violation]
    comfort_net_rows = comfort_alignment_net.loc[comfort_violation]

    guard_fraction = (
        bool_fraction(df["tes_guard_clipped"]) if "tes_guard_clipped" in df.columns else None
    )

    return {
        "label": label,
        "path": str(path),
        "rows": int(len(df)),
        "target_column": target_col,
        "weight": float(args.weight),
        "price_q25": float(price_current.quantile(0.25)),
        "price_q75": float(price_current.quantile(0.75)),
        "low_price_rows": int(low_price.sum()),
        "high_price_rows": int(high_price.sum()),
        "desired_low_charge_rows": int((desired < 0.0).sum()),
        "desired_high_discharge_rows": int((desired > 0.0).sum()),
        "alignment_mean": float(alignment.mean()),
        "alignment_sum": float(alignment.sum()),
        "low_discharge_count": int(low_discharge.sum()),
        "low_discharge_alignment_mean": mean_or_none(alignment.loc[low_discharge]),
        "high_charge_count": int(high_charge.sum()),
        "high_charge_alignment_mean": mean_or_none(alignment.loc[high_charge]),
        "low_charge_count": int(low_charge.sum()),
        "low_charge_alignment_mean": mean_or_none(alignment.loc[low_charge]),
        "high_discharge_count": int(high_discharge.sum()),
        "high_discharge_alignment_mean": mean_or_none(alignment.loc[high_discharge]),
        "target_low_price_mean": mean_or_none(target.loc[low_price]),
        "target_high_price_mean": mean_or_none(target.loc[high_price]),
        "actual_low_price_mean": mean_or_none(actual.loc[low_price]),
        "actual_high_price_mean": mean_or_none(actual.loc[high_price]),
        "actual_price_response_high_minus_low": (
            mean_or_none(actual.loc[high_price]) - mean_or_none(actual.loc[low_price])
            if mean_or_none(actual.loc[high_price]) is not None
            and mean_or_none(actual.loc[low_price]) is not None
            else None
        ),
        "comfort_violation_pct": float(comfort_violation.mean() * 100.0),
        "comfort_violation_alignment_mean": mean_or_none(comfort_rows),
        "comfort_violation_net_mean": mean_or_none(comfort_net_rows),
        "guard_clipped_fraction": guard_fraction,
    }


def build_gates(traces: dict[str, dict[str, Any]]) -> dict[str, bool]:
    learned = traces["learned"]
    rule = traces["rule_tou"]
    neutral = traces["neutral"]

    comfort_ok = True
    for trace in traces.values():
        net = trace.get("comfort_violation_net_mean")
        if net is not None and net > 0.0:
            comfort_ok = False

    return {
        "rule_alignment_mean_gt_learned": (
            rule["alignment_mean"] > learned["alignment_mean"]
        ),
        "learned_low_discharge_penalized": (
            learned["low_discharge_count"] > 0
            and learned["low_discharge_alignment_mean"] is not None
            and learned["low_discharge_alignment_mean"] < 0.0
        ),
        "rule_high_discharge_rewarded": (
            rule["high_discharge_count"] > 0
            and rule["high_discharge_alignment_mean"] is not None
            and rule["high_discharge_alignment_mean"] > 0.0
        ),
        "rule_low_charge_rewarded": (
            rule["low_charge_count"] > 0
            and rule["low_charge_alignment_mean"] is not None
            and rule["low_charge_alignment_mean"] > 0.0
        ),
        "neutral_alignment_near_zero": abs(neutral["alignment_mean"]) <= 1.0e-9,
        "comfort_violation_net_nonpositive": comfort_ok,
    }


def build_alignment_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit a candidate TES TOU alignment reward on three traces.")
    parser.add_argument("--learned", type=Path, required=True)
    parser.add_argument("--rule-tou", type=Path, required=True)
    parser.add_argument("--neutral", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--weight", type=float, default=0.05)
    parser.add_argument("--high-price-threshold", type=float, default=0.75)
    parser.add_argument("--low-price-threshold", type=float, default=-0.50)
    parser.add_argument("--near-peak-threshold", type=float, default=0.40)
    parser.add_argument("--soc-charge-limit", type=float, default=0.85)
    parser.add_argument("--soc-discharge-limit", type=float, default=0.20)
    parser.add_argument("--active-threshold", type=float, default=0.01)
    parser.add_argument("--comfort-high", type=float, default=25.0)
    return parser


def build_window_audit_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Extract reward decomposition around TES TOU window starts.")
    parser.add_argument("monitors", nargs="+", type=Path, help="One or more monitor.csv files.")
    parser.add_argument("--out", type=Path, required=True, help="JSON output path.")
    parser.add_argument("--csv-out", type=Path, required=True, help="CSV detail output path.")
    parser.add_argument("--context-steps", type=int, default=8, help="Steps before/after each window start to emit.")
    parser.add_argument("--high-price-threshold", type=float, default=0.75)
    parser.add_argument("--low-price-threshold", type=float, default=-0.50)
    parser.add_argument("--near-peak-threshold", type=float, default=0.40)
    parser.add_argument("--soc-charge-limit", type=float, default=0.85)
    parser.add_argument("--soc-discharge-limit", type=float, default=0.20)
    return parser


def cmd_alignment_audit(args: argparse.Namespace) -> int:
    traces = {
        "learned": summarize_trace("learned", args.learned, args),
        "rule_tou": summarize_trace("rule_tou", args.rule_tou, args),
        "neutral": summarize_trace("neutral", args.neutral, args),
    }
    gates = build_gates(traces)
    result = {
        "title": "M2-F1 TES TOU reward audit",
        "candidate_term": "weight * desired_sign * tes_valve_target",
        "note": (
            "This is an action-dependent auxiliary term, not PBRS. "
            "It is intended for curriculum/shaping experiments only."
        ),
        "passed": bool(all(gates.values())),
        "gates": gates,
        "traces": traces,
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    print(f"Wrote {args.out}")
    return 0


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "window-audit":
        args = build_window_audit_parser().parse_args(sys.argv[2:])
        raise SystemExit(cmd_window_audit(args))
    if len(sys.argv) > 1 and sys.argv[1] == "alignment-audit":
        args = build_alignment_parser().parse_args(sys.argv[2:])
        raise SystemExit(cmd_alignment_audit(args))

    # Preserve the original flag-only CLI for existing offline audit commands.
    args = build_alignment_parser().parse_args()
    raise SystemExit(cmd_alignment_audit(args))


if __name__ == "__main__":
    main()
