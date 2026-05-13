"""Audit Phase 3 PV-TES technical sizing results."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


def audit_phase3_results(summary_path: str | Path, output_path: str | Path) -> Path:
    summary_path = Path(summary_path)
    output_path = Path(output_path)
    frame = pd.read_csv(summary_path)
    p0: list[str] = []
    p1: list[str] = []
    p2: list[str] = []

    _check_coverage(frame, p0)
    _check_pairs(frame, p0)
    _check_disabled_assets(frame, p0)
    _check_numeric_health(frame, p0, p1)
    _check_soc(frame, p1)
    _check_recommendations(summary_path, frame, p0, p1)

    lines = [
        "# Phase 3 Audit Report",
        "",
        f"Summary file: `{summary_path}`",
        "",
        f"P0 errors: {len(p0)}",
        f"P1 warnings: {len(p1)}",
        f"P2 notes: {len(p2)}",
        "",
    ]
    lines.extend(_section("P0 Errors", p0))
    lines.extend(_section("P1 Warnings", p1))
    lines.extend(_section("P2 Notes", p2))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output_path


def _check_coverage(frame: pd.DataFrame, p0: list[str]) -> None:
    for location_id, group in frame.groupby("location_id"):
        pv = sorted(group["pv_capacity_mwp"].unique())
        tes = sorted(group["tes_capacity_mwh_th"].unique())
        cp = sorted(group["critical_peak_uplift"].unique())
        expected = len(pv) * len(tes) * len(cp)
        actual = len(group[["pv_capacity_mwp", "tes_capacity_mwh_th", "critical_peak_uplift"]].drop_duplicates())
        if actual != expected:
            p0.append(f"{location_id}: coverage mismatch, expected {expected} unique combinations, found {actual}.")


def _check_pairs(frame: pd.DataFrame, p0: list[str]) -> None:
    grouped = frame.groupby(["location_id", "pv_capacity_mwp", "tes_capacity_mwh_th"])
    for key, group in grouped:
        cp_values = set(float(v) for v in group["critical_peak_uplift"])
        if 0.0 in cp_values and 0.2 not in cp_values:
            p0.append(f"{key}: cp_uplift=0.0 exists without cp_uplift=0.2 pair.")
        if 0.2 in cp_values and 0.0 not in cp_values:
            p0.append(f"{key}: cp_uplift=0.2 exists without cp_uplift=0.0 pair.")


def _check_disabled_assets(frame: pd.DataFrame, p0: list[str]) -> None:
    tes0 = frame[frame["tes_capacity_mwh_th"] == 0]
    for col in ("tes_charge_kwh_th", "tes_discharge_kwh_th"):
        bad = tes0[tes0[col].abs() > 1e-7]
        if not bad.empty:
            p0.append(f"TES=0 has nonzero {col}: {len(bad)} cases.")
    pv0 = frame[frame["pv_capacity_mwp"] == 0]
    for col in ("pv_generation_kwh", "pv_spill_kwh", "pv_used_kwh"):
        bad = pv0[pv0[col].abs() > 1e-7]
        if not bad.empty:
            p0.append(f"PV=0 has nonzero {col}: {len(bad)} cases.")


def _check_numeric_health(frame: pd.DataFrame, p0: list[str], p1: list[str]) -> None:
    finite_cols = [
        "grid_balance_max_abs_error_kw",
        "signed_valve_violation_max",
        "pv_self_consumption_ratio",
        "critical_peak_suppression_ratio",
    ]
    for col in finite_cols:
        if col not in frame.columns:
            p0.append(f"missing audit column {col}.")
            continue
        values = pd.to_numeric(frame[col], errors="coerce")
        if np.isinf(values).any():
            p0.append(f"{col} contains inf.")
    if "critical_peak_suppression_ratio" in frame.columns:
        active = frame[frame["critical_peak_uplift"] > 0]
        nan_count = int(active["critical_peak_suppression_ratio"].isna().sum())
        if nan_count:
            p1.append(f"critical_peak_suppression_ratio is NaN in {nan_count} active CP cases.")
        negative = active[active["critical_peak_suppression_ratio"] < 0]
        if not negative.empty:
            p1.append(f"critical_peak_suppression_ratio < 0 in {len(negative)} cases.")
    if "pv_self_consumption_ratio" in frame.columns:
        bad = frame[frame["pv_self_consumption_ratio"] > 1.0 + 1e-7]
        if not bad.empty:
            p0.append(f"PV self-consumption ratio > 1 in {len(bad)} cases.")
    if "grid_balance_max_abs_error_kw" in frame.columns:
        bad = frame[frame["grid_balance_max_abs_error_kw"].abs() > 1e-6]
        if not bad.empty:
            p0.append(f"grid balance violation in {len(bad)} cases.")
    if "signed_valve_violation_max" in frame.columns:
        bad = frame[frame["signed_valve_violation_max"] > 1e-7]
        if not bad.empty:
            p0.append(f"signed valve violation in {len(bad)} cases.")


def _check_soc(frame: pd.DataFrame, p1: list[str]) -> None:
    if "soc_delta" not in frame.columns:
        p1.append("soc_delta column missing.")
        return
    bad = frame[frame["soc_delta"].abs() > 0.05 + 1e-9]
    if not bad.empty:
        p1.append(f"SOC delta exceeds 0.05 in {len(bad)} cases.")


def _check_recommendations(summary_path: Path, frame: pd.DataFrame, p0: list[str], p1: list[str]) -> None:
    rec_path = summary_path.with_name("phase3_capacity_recommendations.csv")
    if not rec_path.exists():
        p1.append("recommendation file not found.")
        return
    recs = pd.read_csv(rec_path)
    for _, rec in recs.iterrows():
        mask = (
            (frame["location_id"] == rec["location_id"])
            & (frame["pv_capacity_mwp"] == rec["recommended_pv_mwp"])
            & (frame["tes_capacity_mwh_th"] == rec["recommended_tes_mwh_th"])
            & (frame["critical_peak_uplift"] > 0)
        )
        rows = frame[mask]
        if rows.empty:
            p0.append(f"{rec['location_id']}: recommended capacity not found in summary.")
        elif not bool(rows.iloc[0].get("is_pareto_frontier", False)):
            p0.append(f"{rec['location_id']}: recommended capacity is not on Pareto frontier.")


def _section(title: str, values: list[str]) -> list[str]:
    lines = [f"## {title}", ""]
    if not values:
        lines.append("None.")
    else:
        lines.extend(f"- {item}" for item in values)
    lines.append("")
    return lines


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    print(audit_phase3_results(args.summary, args.output))


if __name__ == "__main__":
    main()
