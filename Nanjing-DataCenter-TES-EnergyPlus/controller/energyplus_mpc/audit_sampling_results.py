"""Audit EnergyPlus MPC sampling and model-fitting artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from .common import read_yaml
from .run_sampling_matrix import DEFAULT_SAMPLING_ROOT


def audit_sampling_root(root: str | Path) -> list[str]:
    result_root = Path(root)
    issues: list[str] = []
    manifest_path = result_root / "sampling_manifest.csv"
    samples_path = result_root / "samples_15min.csv"
    models_path = result_root / "prediction_models.yaml"
    metrics_path = result_root / "fit_metrics.csv"
    for path in [manifest_path, samples_path, models_path, metrics_path]:
        if not path.exists():
            issues.append(f"missing artifact: {path}")
    if issues:
        return issues
    manifest = pd.read_csv(manifest_path)
    if len(manifest) != 23:
        issues.append(f"expected 23 manifest rows, found {len(manifest)}")
    if manifest["case_id"].duplicated().any():
        issues.append("sampling manifest contains duplicate case_id")
    runnable = manifest[manifest["run_mode"] == "energyplus_runtime"]
    if len(runnable) != 22:
        issues.append(f"expected 22 runnable sampling cases, found {len(runnable)}")
    if not manifest.loc[manifest["family"] != "baseline_reuse", "identification_only"].astype(bool).all():
        issues.append("non-baseline sampling rows must be identification_only=true")
    samples = pd.read_csv(samples_path)
    required_cols = ["case_id", "timestamp", "split", "tes_set_written", "ite_set_written", "chiller_t_set_written", "soc"]
    missing_cols = [col for col in required_cols if col not in samples]
    if missing_cols:
        issues.append(f"samples_15min.csv missing columns: {missing_cols}")
    if "split" in samples and set(samples["split"].unique()) - {"train", "validation"}:
        issues.append("samples split must contain only train/validation")
    models = read_yaml(models_path)
    if models.get("split_method") != "date_block_dayofyear_mod_5_validation":
        issues.append("prediction model split method is not date-blocked")
    if not models.get("adoption_ready", False) and not models.get("failure_reasons"):
        issues.append("non-adoption-ready prediction models must record failure_reasons")
    metrics = pd.read_csv(metrics_path)
    for model in ["chiller_power", "soc_24h_rollout", "tes_direction"]:
        if model not in set(metrics["model"]):
            issues.append(f"fit metrics missing {model}")
    figure_dir = result_root / "figures"
    if not figure_dir.exists() or not list(figure_dir.glob("*.png")):
        issues.append("sampling figures directory is missing PNG diagnostics")
    for case_dir in sorted(p.parent for p in result_root.glob("*/monitor.csv")):
        _audit_case_dir(case_dir, issues)
    return issues


def _audit_case_dir(case_dir: Path, issues: list[str]) -> None:
    required = ["monitor.csv", "mpc_action.csv", "observation.csv", "summary.csv", "run_manifest.json", "handle_map.json"]
    missing = [name for name in required if not (case_dir / name).exists()]
    if missing:
        issues.append(f"{case_dir.name}: missing {missing}")
        return
    handle_map = json.loads((case_dir / "handle_map.json").read_text(encoding="utf-8"))
    if handle_map.get("missing"):
        issues.append(f"{case_dir.name}: unresolved runtime handles {handle_map['missing']}")
    summary = pd.read_csv(case_dir / "summary.csv").iloc[0].to_dict()
    if int(summary.get("exit_code", -1)) != 0:
        issues.append(f"{case_dir.name}: EnergyPlus exit code {summary.get('exit_code')}")
    for key in ["tes_set_mismatch_count", "ite_set_mismatch_count", "chiller_t_set_mismatch_count"]:
        if int(summary.get(key, 0)) != 0:
            issues.append(f"{case_dir.name}: {key}={summary.get(key)}")
    warning_path = case_dir / "warning_summary.json"
    if warning_path.exists():
        warnings = json.loads(warning_path.read_text(encoding="utf-8"))
        if int(warnings.get("severe_errors", 0)) != 0:
            issues.append(f"{case_dir.name}: EnergyPlus severe errors")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(DEFAULT_SAMPLING_ROOT))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    issues = audit_sampling_root(args.root)
    if issues:
        for issue in issues:
            print(f"FAIL: {issue}")
        return 1
    print(f"EnergyPlus-MPC sampling audit passed: {args.root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
