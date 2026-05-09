"""Run seasonal EnergyPlus-MPC controller comparison matrix."""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from .common import DEFAULT_PARAM_YAML, DEFAULT_SELECTED_ROOT, EPLUS_ROOT, read_yaml, write_yaml
from .mpc_adapter import derive_measured_params
from .run_energyplus_mpc import EnergyPlusMpcRunner


DEFAULT_MATRIX_ROOT = DEFAULT_SELECTED_ROOT.parent / "energyplus_mpc_controller_matrix_20260508"
DEFAULT_PREDICTION_MODEL = DEFAULT_SELECTED_ROOT.parent / "energyplus_mpc_sampling_20260507" / "prediction_models.yaml"
DEFAULT_SAMPLES = DEFAULT_SELECTED_ROOT.parent / "energyplus_mpc_sampling_20260507" / "samples_15min.csv"
DEFAULT_REPORT_PATH = DEFAULT_SELECTED_ROOT.parents[1] / "docs" / "energyplus_mpc_controller_matrix_report_20260508.md"
HARDENED_REPORT_PATH = DEFAULT_SELECTED_ROOT.parents[1] / "docs" / "energyplus_mpc_controller_matrix_hardening_report_20260509.md"

SEASON_WINDOWS = {
    "winter": {"month": "January", "record_start_step": 0},
    "spring": {"month": "April", "record_start_step": 8640},
    "summer": {"month": "July", "record_start_step": 17376},
    "autumn": {"month": "October", "record_start_step": 26208},
}
CONTROLLERS = ("no_mpc", "default_mpc", "measured_data_mpc")


def build_matrix_manifest(seasons: list[str], days: int, smoke: bool = False) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    steps = int(days) * 96
    selected = ["winter"] if smoke else seasons
    prefix = "smoke_" if smoke else ""
    for season in selected:
        window = SEASON_WINDOWS[season]
        for controller in CONTROLLERS:
            source = "none" if controller == "no_mpc" else "default_proxy"
            if controller == "measured_data_mpc":
                source = "measured_sampling"
            case_id = f"{prefix}{season}_{controller}"
            rows.append(
                {
                    "case_id": case_id,
                    "season": season,
                    "month": window["month"],
                    "controller": controller,
                    "model_source": source,
                    "record_start_step": window["record_start_step"],
                    "max_steps": steps,
                    "days": int(days),
                    "smoke": bool(smoke),
                }
            )
    return pd.DataFrame(rows)


def run_matrix(
    output_root: str | Path,
    seasons: list[str],
    days: int,
    smoke: bool,
    overwrite: bool = False,
    prediction_model_path: str | Path = DEFAULT_PREDICTION_MODEL,
    samples_path: str | Path = DEFAULT_SAMPLES,
) -> Path:
    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=True)
    manifest = build_matrix_manifest(seasons, days, smoke)
    manifest.to_csv(root / "matrix_manifest.csv", index=False)
    measured_params = _write_measured_params(root, prediction_model_path, samples_path)
    for row in manifest.to_dict("records"):
        case_dir = root / row["case_id"]
        if (case_dir / "summary.csv").exists() and not overwrite:
            continue
        raw_dir = EPLUS_ROOT / "out" / "energyplus_controller_matrix_20260508" / row["case_id"]
        params_path = measured_params if row["controller"] == "measured_data_mpc" else DEFAULT_PARAM_YAML
        runner = EnergyPlusMpcRunner(
            controller=row["controller"],
            max_steps=int(row["max_steps"]),
            eplus_root="C:/Users/18430/EnergyPlus-23.1.0/EnergyPlus-23.1.0-87ed9199d4-Windows-x86_64",
            model=EPLUS_ROOT / "model" / "Nanjing_DataCenter_TES.epJSON",
            weather=EPLUS_ROOT / "weather" / "CHN_JS_Nanjing.582380_TMYx.2009-2023.epw",
            params_path=params_path,
            baseline_timeseries=EPLUS_ROOT / "out" / "energyplus_nanjing" / "timeseries_15min.csv",
            price_csv=EPLUS_ROOT / "inputs" / "Jiangsu_TOU_2025_hourly.csv",
            pv_csv=EPLUS_ROOT / "inputs" / "CHN_Nanjing_PV_6MWp_hourly.csv",
            raw_output_dir=raw_dir,
            selected_output_root=root,
            horizon_steps=8,
            mode_integrality="relaxed",
            load_forecast="baseline",
            record_start_step=int(row["record_start_step"]),
            case_name=row["case_id"],
            run_metadata={
                "matrix_case_id": row["case_id"],
                "matrix_season": row["season"],
                "matrix_controller": row["controller"],
                "model_source": row["model_source"],
                "prediction_model_path": str(prediction_model_path) if row["controller"] == "measured_data_mpc" else "",
                "matrix_days": int(row["days"]),
                "smoke": bool(row["smoke"]),
            },
        )
        runner.run()
    _write_summaries(root, manifest)
    _write_report(root, manifest)
    return root


def _write_measured_params(root: Path, prediction_model_path: str | Path, samples_path: str | Path) -> Path:
    params = read_yaml(DEFAULT_PARAM_YAML)
    measured = derive_measured_params(params, prediction_model_path, samples_path)
    config_dir = root / "_configs"
    config_dir.mkdir(parents=True, exist_ok=True)
    path = config_dir / "measured_data_mpc_params.yaml"
    write_yaml(path, measured)
    return path


def _write_summaries(root: Path, manifest: pd.DataFrame) -> None:
    rows: list[dict[str, Any]] = []
    for item in manifest.to_dict("records"):
        summary_path = root / item["case_id"] / "summary.csv"
        if not summary_path.exists():
            continue
        row = pd.read_csv(summary_path).iloc[0].to_dict()
        _ensure_temperature_kpis(root / item["case_id"], row)
        row.update({k: item[k] for k in ["case_id", "season", "month", "controller", "model_source"]})
        _add_diagnostic_role(row)
        rows.append(row)
    summary = pd.DataFrame(rows)
    summary.to_csv(root / "season_summary.csv", index=False)
    comparisons: list[dict[str, Any]] = []
    if summary.empty:
        pd.DataFrame().to_csv(root / "comparison_summary.csv", index=False)
        return
    for season, group in summary.groupby("season"):
        baseline = group[group["controller"] == "no_mpc"]
        if baseline.empty:
            continue
        base = baseline.iloc[0]
        controllers = sorted(str(item) for item in group["controller"].unique() if str(item) != "no_mpc")
        for controller in controllers:
            current = group[group["controller"] == controller]
            if current.empty:
                continue
            row = current.iloc[0]
            temp_delta = float(row["temp_violation_degree_hours_27c"] - base["temp_violation_degree_hours_27c"])
            temp_max_delta = float(row["zone_temp_max_c"] - base["zone_temp_max_c"])
            comparison_valid = bool(temp_delta <= 1e-6 and temp_max_delta <= 1e-6)
            comparisons.append(
                {
                    "season": season,
                    "controller": controller,
                    "result_role": "io_coupling_diagnostic",
                    "cost_saving": float(base["pv_adjusted_cost"] - row["pv_adjusted_cost"]),
                    "cost_saving_pct": _pct(base["pv_adjusted_cost"] - row["pv_adjusted_cost"], base["pv_adjusted_cost"]),
                    "cost_saving_claim": ""
                    if not comparison_valid
                    else f"{float(base['pv_adjusted_cost'] - row['pv_adjusted_cost']):.6g}",
                    "grid_saving_kwh": float(base["pv_adjusted_grid_kwh"] - row["pv_adjusted_grid_kwh"]),
                    "grid_saving_pct": _pct(base["pv_adjusted_grid_kwh"] - row["pv_adjusted_grid_kwh"], base["pv_adjusted_grid_kwh"]),
                    "peak_grid_reduction_kw": float(base["peak_grid_kw"] - row["peak_grid_kw"]),
                    "peak_grid_reduction_pct": _pct(base["peak_grid_kw"] - row["peak_grid_kw"], base["peak_grid_kw"]),
                    "fallback_count": int(row.get("fallback_count", 0)),
                    "io_success_flag": bool(row.get("io_success_flag", False)),
                    "tes_set_echo_ok": bool(row.get("tes_set_echo_ok", False)),
                    "chiller_t_set_echo_ok": bool(row.get("chiller_t_set_echo_ok", False)),
                    "temperature_safe_flag": bool(row.get("temperature_safe_flag", False)),
                    "soc_min": float(row["soc_min"]),
                    "soc_final": float(row["soc_final"]),
                    "zone_temp_max_c": float(row["zone_temp_max_c"]),
                    "temp_violation_degree_hours_27c": float(row["temp_violation_degree_hours_27c"]),
                    "temp_violation_delta_vs_no_mpc": temp_delta,
                    "zone_temp_max_delta_vs_no_mpc": temp_max_delta,
                    "cost_comparison_valid": comparison_valid,
                }
            )
    pd.DataFrame(comparisons).to_csv(root / "comparison_summary.csv", index=False)


def _pct(delta: float, base: float) -> float:
    return float(delta / base * 100.0) if abs(base) > 1e-9 else 0.0


def _add_diagnostic_role(row: dict[str, Any]) -> None:
    row["result_role"] = "io_coupling_diagnostic"
    row["tes_set_echo_ok"] = int(row.get("tes_set_mismatch_count", -1)) == 0
    if "chiller_t_set_mismatch_count" in row:
        row["chiller_t_set_echo_ok"] = int(row.get("chiller_t_set_mismatch_count", -1)) == 0
    else:
        row["chiller_t_set_echo_ok"] = True
    row["temperature_safe_flag"] = bool(row.get("valid_comfort_flag", False))
    row["io_success_flag"] = (
        int(row.get("exit_code", -1)) == 0
        and int(row.get("fallback_count", 0)) == 0
        and bool(row["tes_set_echo_ok"])
        and bool(row["chiller_t_set_echo_ok"])
    )


def _ensure_temperature_kpis(case_dir: Path, row: dict[str, Any]) -> None:
    if "temp_violation_degree_hours_27c" in row and "valid_comfort_flag" in row:
        return
    monitor_path = case_dir / "monitor.csv"
    if not monitor_path.exists():
        row.setdefault("temp_violation_threshold_c", 27.0)
        row.setdefault("temp_violation_degree_hours_27c", float("nan"))
        row.setdefault("valid_comfort_flag", False)
        return
    monitor = pd.read_csv(monitor_path, usecols=["zone_temp_c"])
    threshold = 27.0
    degree_hours = float(((monitor["zone_temp_c"] - threshold).clip(lower=0.0) * 0.25).sum())
    row["temp_violation_threshold_c"] = threshold
    row["temp_violation_degree_hours_27c"] = degree_hours
    row["valid_comfort_flag"] = bool(degree_hours <= 1e-9)


def _write_report(root: Path, manifest: pd.DataFrame) -> None:
    summary = pd.read_csv(root / "season_summary.csv") if (root / "season_summary.csv").exists() else pd.DataFrame()
    comparison = pd.read_csv(root / "comparison_summary.csv") if (root / "comparison_summary.csv").exists() else pd.DataFrame()
    report_path = _report_path_for_root(root)
    report_date = "2026-05-09" if "hardened_20260509" in root.name else "2026-05-08"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        "\n".join(
            [
                f"# EnergyPlus-MPC Controller Matrix Report {report_date}",
                "",
                "## Summary",
                "",
                f"- Result root: `{root}`",
                f"- Matrix cases expected: `{len(manifest)}`",
                f"- Matrix cases completed: `{len(summary)}`",
                "- Result role: `io_coupling_diagnostic`; these rows verify I/O coupling and temperature risk, not final saving claims.",
                "- Controllers: " + ", ".join(f"`{item}`" for item in sorted(manifest["controller"].unique())),
                "- This matrix compares four seasonal month windows and is not a full-year saving claim.",
                "- Cost saving rows are valid as control-benefit evidence only when `cost_comparison_valid=true`; current EnergyPlus online results are otherwise coupling feasibility plus temperature-safety diagnostics.",
                "",
                "## Season Summary",
                "",
                _frame_to_markdown(summary),
                "",
                "## Comparison Against no_mpc",
                "",
                _frame_to_markdown(comparison),
                "",
                "## Thesis Impact",
                "",
                "No thesis draft update is required until these matrix results are explicitly adopted as thesis conclusions.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def _report_path_for_root(root: Path) -> Path:
    if "hardened_20260509" in root.name:
        return HARDENED_REPORT_PATH
    return DEFAULT_REPORT_PATH


def _frame_to_markdown(frame: pd.DataFrame) -> str:
    if frame.empty:
        return "_No rows._"
    columns = list(frame.columns)
    lines = ["| " + " | ".join(columns) + " |", "| " + " | ".join(["---"] * len(columns)) + " |"]
    for row in frame.to_dict("records"):
        lines.append("| " + " | ".join(str(row[col]) for col in columns) + " |")
    return "\n".join(lines)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", default=str(DEFAULT_MATRIX_ROOT))
    parser.add_argument("--seasons", default="winter,spring,summer,autumn")
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--prediction-model", default=str(DEFAULT_PREDICTION_MODEL))
    parser.add_argument("--samples", default=str(DEFAULT_SAMPLES))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    seasons = [item.strip() for item in args.seasons.split(",") if item.strip()]
    unknown = [season for season in seasons if season not in SEASON_WINDOWS]
    if unknown:
        raise ValueError(f"unknown seasons: {unknown}")
    root = run_matrix(args.output_root, seasons, args.days, args.smoke, args.overwrite, args.prediction_model, args.samples)
    print(root)
    print(_report_path_for_root(Path(root)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
