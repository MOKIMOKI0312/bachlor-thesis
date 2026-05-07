"""Audit selected EnergyPlus-MPC result artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


def audit_root(root: str | Path) -> list[str]:
    result_root = Path(root)
    issues: list[str] = []
    for controller in ["no_control", "rbc", "mpc"]:
        case = result_root / controller
        if not case.exists():
            issues.append(f"missing case directory: {case}")
            continue
        _audit_case(case, controller, issues)
    perturbation = result_root / "perturbation"
    if perturbation.exists():
        _audit_case(perturbation, "perturbation", issues)
    return issues


def _audit_case(case: Path, controller: str, issues: list[str]) -> None:
    required = ["monitor.csv", "observation.csv", "mpc_action.csv", "solver_log.csv", "summary.csv", "run_manifest.json", "handle_map.json"]
    local_missing = []
    for name in required:
        if not (case / name).exists():
            local_missing.append(name)
    if local_missing:
        issues.extend(f"{case.name}: missing {name}" for name in local_missing)
        return
    monitor = pd.read_csv(case / "monitor.csv")
    summary = pd.read_csv(case / "summary.csv").iloc[0].to_dict()
    handle_map = json.loads((case / "handle_map.json").read_text(encoding="utf-8"))
    if handle_map.get("missing"):
        issues.append(f"{case.name}: unresolved handles {handle_map['missing']}")
    if int(summary.get("steps", 0)) < 1:
        issues.append(f"{case.name}: no recorded steps")
    if int(summary.get("exit_code", -1)) != 0:
        issues.append(f"{case.name}: EnergyPlus exit code {summary.get('exit_code')}")
    if "tes_set_written" in monitor and int(summary.get("tes_set_mismatch_count", -1)) != 0:
        issues.append(f"{case.name}: TES_Set echo mismatch")
    if monitor["soc"].min() < -1e-6 or monitor["soc"].max() > 1.0 + 1e-6:
        issues.append(f"{case.name}: SOC out of physical [0, 1] range")
    if monitor["zone_temp_c"].min() < 5.0 or monitor["zone_temp_c"].max() > 40.0:
        issues.append(f"{case.name}: zone temperature outside broad sanity range")
    if controller == "mpc" and int(summary.get("fallback_count", -1)) != 0:
        issues.append(f"{case.name}: MPC fallback count {summary.get('fallback_count')}")
    if controller in {"rbc", "mpc"}:
        active_charge = (monitor["tes_set_written"] < -0.01).any()
        active_discharge = (monitor["tes_set_written"] > 0.01).any()
        if not (active_charge or active_discharge):
            issues.append(f"{case.name}: no nonzero TES control actions")
        if active_discharge and int(summary.get("tes_use_response_count", 0)) <= 0:
            issues.append(f"{case.name}: TES_Set > 0 did not produce use-side response")
        if active_charge and int(summary.get("tes_source_response_count", 0)) <= 0:
            issues.append(f"{case.name}: TES_Set < 0 did not produce source-side response")
    if controller == "perturbation":
        if not (monitor["tes_set_written"] > 0.01).any():
            issues.append(f"{case.name}: missing positive TES_Set pulse")
        if not (monitor["tes_set_written"] < -0.01).any():
            issues.append(f"{case.name}: missing negative TES_Set pulse")
        if int(summary.get("tes_use_response_count", 0)) <= 0:
            issues.append(f"{case.name}: positive TES_Set pulse did not produce use-side response")
        if int(summary.get("tes_source_response_count", 0)) <= 0:
            issues.append(f"{case.name}: negative TES_Set pulse did not produce source-side response")
    warning_path = case / "warning_summary.json"
    if warning_path.exists():
        warnings = json.loads(warning_path.read_text(encoding="utf-8"))
        if int(warnings.get("severe_errors", 0)) != 0:
            issues.append(f"{case.name}: severe errors in EnergyPlus output")
        for key in ["tower_approach_out_of_range", "tower_range_out_of_range", "wetbulb_out_of_range"]:
            if int(warnings.get(key, 0)) != 0:
                issues.append(f"{case.name}: cooling tower warning regression {key}")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    issues = audit_root(args.root)
    if issues:
        for issue in issues:
            print(f"FAIL: {issue}")
        return 1
    print(f"EnergyPlus-MPC audit passed: {args.root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
