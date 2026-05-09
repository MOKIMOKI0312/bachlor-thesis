"""Audit seasonal EnergyPlus-MPC controller matrix outputs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


REQUIRED_CASE_FILES = [
    "monitor.csv",
    "observation.csv",
    "mpc_action.csv",
    "solver_log.csv",
    "summary.csv",
    "summary.json",
    "run_manifest.json",
    "handle_map.json",
    "warning_summary.json",
]


def audit_matrix_root(root: str | Path) -> list[str]:
    result_root = Path(root)
    issues: list[str] = []
    manifest_path = result_root / "matrix_manifest.csv"
    if not manifest_path.exists():
        return [f"missing matrix manifest: {manifest_path}"]
    manifest = pd.read_csv(manifest_path)
    for row in manifest.to_dict("records"):
        _audit_case(result_root / row["case_id"], row, issues)
    _audit_summaries(result_root, manifest, issues)
    return issues


def _audit_case(case_dir: Path, manifest_row: dict, issues: list[str]) -> None:
    if not case_dir.exists():
        issues.append(f"missing case directory: {case_dir}")
        return
    missing = [name for name in REQUIRED_CASE_FILES if not (case_dir / name).exists()]
    if missing:
        issues.extend(f"{case_dir.name}: missing {name}" for name in missing)
        return
    monitor = pd.read_csv(case_dir / "monitor.csv")
    summary = pd.read_csv(case_dir / "summary.csv").iloc[0].to_dict()
    run_manifest = json.loads((case_dir / "run_manifest.json").read_text(encoding="utf-8"))
    handle_map = json.loads((case_dir / "handle_map.json").read_text(encoding="utf-8"))
    warnings = json.loads((case_dir / "warning_summary.json").read_text(encoding="utf-8"))
    if handle_map.get("missing"):
        issues.append(f"{case_dir.name}: unresolved handles {handle_map['missing']}")
    if int(summary.get("exit_code", -1)) != 0:
        issues.append(f"{case_dir.name}: EnergyPlus exit code {summary.get('exit_code')}")
    if int(summary.get("steps", 0)) != int(manifest_row["max_steps"]):
        issues.append(f"{case_dir.name}: steps {summary.get('steps')} != expected {manifest_row['max_steps']}")
    if int(summary.get("record_start_step", -1)) != int(manifest_row["record_start_step"]):
        issues.append(f"{case_dir.name}: record_start_step mismatch")
    if int(warnings.get("severe_errors", 0)) != 0:
        issues.append(f"{case_dir.name}: severe errors in EnergyPlus output")
    if int(summary.get("tes_set_mismatch_count", -1)) != 0:
        issues.append(f"{case_dir.name}: TES_Set echo mismatch")
    if "temp_violation_degree_hours_27c" not in summary:
        issues.append(f"{case_dir.name}: missing temp_violation_degree_hours_27c")
    if monitor["soc"].min() < -1e-6 or monitor["soc"].max() > 1.0 + 1e-6:
        issues.append(f"{case_dir.name}: SOC outside physical [0, 1] range")
    if monitor["zone_temp_c"].min() < 5.0 or monitor["zone_temp_c"].max() > 40.0:
        issues.append(f"{case_dir.name}: zone temperature outside broad sanity range")
    controller = str(manifest_row["controller"])
    control_surface = {item.strip() for item in str(run_manifest.get("control_surface", "")).split(",") if item.strip()}
    if controller == "no_mpc" and (monitor["tes_set_written"].abs() > 1e-9).any():
        issues.append(f"{case_dir.name}: no_mpc wrote nonzero TES_Set")
    if controller == "no_mpc" and "chiller_t_set_written" in monitor and monitor["chiller_t_set_written"].notna().any():
        issues.append(f"{case_dir.name}: no_mpc wrote Chiller_T_Set")
    if "mpc" in controller and controller != "no_mpc" and int(summary.get("fallback_count", -1)) != 0:
        issues.append(f"{case_dir.name}: MPC fallback count {summary.get('fallback_count')}")
    if "chiller_t_set" in control_surface:
        if "chiller_t_set_written" not in monitor:
            issues.append(f"{case_dir.name}: control_surface includes chiller_t_set but monitor has no writes")
        if int(summary.get("chiller_t_set_mismatch_count", -1)) != 0:
            issues.append(f"{case_dir.name}: Chiller_T_Set echo mismatch")
    if controller != "sampling" and "ite_set_written" in monitor and monitor["ite_set_written"].notna().any():
        issues.append(f"{case_dir.name}: normal controller wrote ITE_Set")
    if "measured" in controller:
        if run_manifest.get("model_source") != "measured_sampling":
            issues.append(f"{case_dir.name}: measured controller missing measured model source")
        if not run_manifest.get("prediction_model_path"):
            issues.append(f"{case_dir.name}: measured controller missing prediction_model_path")


def _audit_summaries(root: Path, manifest: pd.DataFrame, issues: list[str]) -> None:
    summary_path = root / "season_summary.csv"
    comparison_path = root / "comparison_summary.csv"
    if not summary_path.exists():
        issues.append("missing season_summary.csv")
        return
    if not comparison_path.exists():
        issues.append("missing comparison_summary.csv")
        return
    summary = pd.read_csv(summary_path)
    comparison = pd.read_csv(comparison_path)
    if len(summary) != len(manifest):
        issues.append(f"season_summary rows {len(summary)} != manifest rows {len(manifest)}")
    expected_controllers = {str(item) for item in manifest["controller"].unique()}
    expected_comparisons = int(
        sum(max(0, len(set(group["controller"])) - (1 if "no_mpc" in set(group["controller"]) else 0)) for _, group in manifest.groupby("season"))
    )
    if len(comparison) != expected_comparisons:
        issues.append(f"comparison_summary rows {len(comparison)} != expected {expected_comparisons}")
    required_comparison_cols = {
        "cost_saving",
        "grid_saving_kwh",
        "peak_grid_reduction_kw",
        "temp_violation_delta_vs_no_mpc",
        "zone_temp_max_delta_vs_no_mpc",
        "cost_comparison_valid",
    }
    missing_cols = required_comparison_cols - set(comparison.columns)
    if missing_cols:
        issues.append(f"comparison_summary missing columns: {sorted(missing_cols)}")
    for season, group in summary.groupby("season"):
        if group["record_start_step"].nunique() != 1:
            issues.append(f"{season}: record_start_step not identical across controllers")
        if group["steps"].nunique() != 1:
            issues.append(f"{season}: steps not identical across controllers")
        expected_for_season = set(manifest.loc[manifest["season"] == season, "controller"])
        if set(group["controller"]) != expected_for_season:
            issues.append(f"{season}: missing controller rows")
    if "controller" in comparison:
        unexpected = set(comparison["controller"]) - (expected_controllers - {"no_mpc"})
        if unexpected:
            issues.append(f"comparison_summary has unexpected controllers: {sorted(unexpected)}")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    issues = audit_matrix_root(args.root)
    if issues:
        for issue in issues:
            print(f"FAIL: {issue}")
        return 1
    print(f"EnergyPlus-MPC controller matrix audit passed: {args.root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
