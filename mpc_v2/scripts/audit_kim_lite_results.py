"""Audit Kim-lite hardened result files for silent validity failures."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd

from mpc_v2.kim_lite.config import load_config


def audit_root(root: str | Path, config_path: str = "mpc_v2/config/kim_lite_base.yaml") -> list[str]:
    cfg = load_config(config_path)
    result_root = Path(root)
    issues: list[str] = []
    _audit_phase_b(result_root, cfg, issues)
    _audit_phase_c(result_root, cfg, issues)
    _audit_phase_d(result_root, cfg, issues)
    return issues


def _audit_phase_b(root: Path, cfg, issues: list[str]) -> None:
    path = root / "phase_b_attribution" / "summary.csv"
    if not path.exists():
        issues.append(f"missing Phase B summary: {path}")
        return
    summary = pd.read_csv(path)
    _require_columns(
        summary,
        path,
        issues,
        [
            "controller",
            "solver_status",
            "soc_final",
            "terminal_soc_abs_error",
            "soc_violation_count",
            "grid_balance_violation_count",
            "signed_valve_violation_count",
            "TES_discharge_during_cp_kwh_th",
            "TES_charge_during_valley_kwh_th",
            "grid_reduction_during_cp_kwh",
            "cp_hours",
        ],
    )
    if issues:
        return
    neutral = summary[summary["controller"] == "storage_priority_neutral_tes"]
    if neutral.empty:
        issues.append("Phase B missing storage_priority_neutral_tes")
    else:
        max_error = float(neutral["terminal_soc_abs_error"].max())
        if max_error > 1e-3:
            issues.append(f"storage_priority_neutral_tes terminal SOC error too high: {max_error}")
    _audit_common_success_rows(summary, cfg, issues, context="Phase B")
    _audit_signed_ramp_mainline(summary, issues, context="Phase B")
    table = root / "phase_b_attribution" / "attribution_table.csv"
    if not table.exists():
        issues.append(f"missing attribution table: {table}")
    else:
        metrics = set(pd.read_csv(table)["metric"])
        for metric in ["RBC_gap_neutral", "RBC_gap_non_neutral"]:
            if metric not in metrics:
                issues.append(f"attribution table missing {metric}")


def _audit_phase_d(root: Path, cfg, issues: list[str]) -> None:
    path = root / "phase_d_peakcap" / "summary.csv"
    if not path.exists():
        issues.append(f"missing Phase D summary: {path}")
        return
    summary = pd.read_csv(path)
    _require_columns(
        summary,
        path,
        issues,
        [
            "controller",
            "solver_status",
            "mode_integrality",
            "strict_success",
            "fallback_reason",
            "mode_fractionality_max",
            "cap_ratio",
            "peak_cap_kw",
            "peak_grid_kw",
            "peak_slack_max_kw",
            "peak_slack_kwh",
            "energy_cost",
            "peak_slack_penalty_cost",
            "objective_cost",
            "peak_cap_success_flag",
            "TES_peak_cap_help_kwh",
            "TES_peak_cap_help_max_kw",
            "soc_violation_count",
            "grid_balance_violation_count",
            "signed_valve_violation_count",
        ],
    )
    if issues:
        return
    for _, row in summary.iterrows():
        label = str(row.get("case_id", "unknown"))
        status = str(row["solver_status"])
        mode_integrality = str(row["mode_integrality"])
        if status == "failed":
            if not str(row.get("fallback_reason", "")).strip():
                issues.append(f"{label}: failed strict/relaxed row lacks fallback_reason")
            continue
        if mode_integrality == "strict":
            if status == "optimal_relaxed_modes":
                issues.append(f"{label}: strict row reported relaxed solver status")
            if float(row["mode_fractionality_max"]) > 1e-6:
                issues.append(f"{label}: strict mode fractionality {row['mode_fractionality_max']}")
            if not bool(row["strict_success"]):
                issues.append(f"{label}: strict row succeeded but strict_success is false")
        elif mode_integrality == "relaxed":
            if status != "optimal_relaxed_modes":
                issues.append(f"{label}: relaxed reference did not report optimal_relaxed_modes")
        else:
            issues.append(f"{label}: unexpected mode_integrality {mode_integrality}")
        if float(row["peak_slack_max_kw"]) < -1e-8:
            issues.append(f"{label}: negative peak slack")
        if float(row["peak_grid_kw"]) > float(row["peak_cap_kw"]) + float(row["peak_slack_max_kw"]) + 1e-5:
            issues.append(f"{label}: peak cap accounting mismatch")
    _audit_common_success_rows(summary, cfg, issues, context="Phase D")
    _audit_signed_ramp_mainline(summary, issues, context="Phase D")


def _audit_phase_c(root: Path, cfg, issues: list[str]) -> None:
    path = root / "phase_c_tou" / "summary.csv"
    if not path.exists():
        return
    summary = pd.read_csv(path)
    _require_columns(
        summary,
        path,
        issues,
        [
            "controller",
            "scenario",
            "TES_discharge_during_cp_kwh_th",
            "TES_charge_during_valley_kwh_th",
            "grid_reduction_during_cp_kwh",
            "cp_hours",
            "signed_valve_violation_count",
        ],
    )
    if issues:
        return
    _audit_common_success_rows(summary, cfg, issues, context="Phase C")
    _audit_signed_ramp_mainline(summary, issues, context="Phase C")


def _audit_common_success_rows(summary: pd.DataFrame, cfg, issues: list[str], context: str) -> None:
    for _, row in summary.iterrows():
        label = str(row.get("case_id", row.get("controller", "unknown")))
        if str(row.get("solver_status", "")) == "failed":
            continue
        if int(row.get("grid_balance_violation_count", -1)) != 0:
            issues.append(f"{context} {label}: grid balance violation")
        if int(row.get("soc_violation_count", -1)) != 0:
            issues.append(f"{context} {label}: SOC violation")
        if "soc_min" in row and float(row["soc_min"]) < cfg.tes.soc_min - 1e-8:
            issues.append(f"{context} {label}: SOC below minimum")
        if "soc_max" in row and float(row["soc_max"]) > cfg.tes.soc_max + 1e-8:
            issues.append(f"{context} {label}: SOC above maximum")
        if not str(row.get("solver_status", "")).strip():
            issues.append(f"{context} {label}: missing solver status")


def _audit_signed_ramp_mainline(summary: pd.DataFrame, issues: list[str], context: str) -> None:
    if "signed_valve_violation_count" not in summary:
        return
    mainline = summary[
        (summary["controller"] == "paper_like_mpc_tes")
        & (summary.get("solver_status", pd.Series("", index=summary.index)).astype(str) != "failed")
    ]
    for _, row in mainline.iterrows():
        count = int(row.get("signed_valve_violation_count", -1))
        if count != 0:
            issues.append(f"{context} {row.get('case_id', 'paper_like_mpc_tes')}: signed valve violation count {count}")


def _require_columns(frame: pd.DataFrame, path: Path, issues: list[str], columns: list[str]) -> None:
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        issues.append(f"{path} missing columns: {', '.join(missing)}")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True)
    parser.add_argument("--config", default="mpc_v2/config/kim_lite_base.yaml")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    issues = audit_root(args.root, args.config)
    if issues:
        for issue in issues:
            print(f"FAIL: {issue}")
        return 1
    print(f"Kim-lite audit passed: {args.root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
