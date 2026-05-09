"""Run EnergyPlus-MPC I/O-coupled controller comparison matrix."""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import pandas as pd

from .common import DEFAULT_PARAM_YAML, DEFAULT_SELECTED_ROOT, EPLUS_ROOT
from .run_controller_matrix import (
    DEFAULT_PREDICTION_MODEL,
    DEFAULT_SAMPLES,
    SEASON_WINDOWS,
    _frame_to_markdown,
    _write_measured_params,
    _write_summaries,
)
from .run_energyplus_mpc import EnergyPlusMpcRunner


DEFAULT_IO_MATRIX_ROOT = DEFAULT_SELECTED_ROOT.parent / "energyplus_mpc_io_coupling_matrix_20260509"
DEFAULT_IO_REPORT_PATH = DEFAULT_SELECTED_ROOT.parents[1] / "docs" / "energyplus_mpc_io_coupling_matrix_report_20260509.md"
CONTROLLERS = ("no_mpc", "tes_only_mpc", "io_coupled_mpc", "io_coupled_measured_mpc")


def build_matrix_manifest(seasons: list[str], days: int, smoke: bool = False) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    steps = int(days) * 96
    selected = ["winter"] if smoke else seasons
    prefix = "smoke_" if smoke else ""
    for season in selected:
        window = SEASON_WINDOWS[season]
        for controller in CONTROLLERS:
            source = "none" if controller == "no_mpc" else "default_proxy"
            prediction_model_path = ""
            if controller == "io_coupled_measured_mpc":
                source = "measured_sampling"
            control_surface = ""
            if controller == "tes_only_mpc":
                control_surface = "tes_set"
            elif controller in {"io_coupled_mpc", "io_coupled_measured_mpc"}:
                control_surface = "tes_set,chiller_t_set"
            case_id = f"{prefix}{season}_{controller}"
            rows.append(
                {
                    "case_id": case_id,
                    "season": season,
                    "month": window["month"],
                    "controller": controller,
                    "model_source": source,
                    "prediction_model_path": prediction_model_path,
                    "control_surface": control_surface,
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
    workers: int = 1,
    prediction_model_path: str | Path = DEFAULT_PREDICTION_MODEL,
    samples_path: str | Path = DEFAULT_SAMPLES,
) -> Path:
    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=True)
    manifest = build_matrix_manifest(seasons, days, smoke)
    manifest.loc[manifest["controller"] == "io_coupled_measured_mpc", "prediction_model_path"] = str(prediction_model_path)
    manifest.to_csv(root / "matrix_manifest.csv", index=False)
    measured_params = _write_measured_params(root, prediction_model_path, samples_path)
    tasks = [
        row
        for row in manifest.to_dict("records")
        if overwrite or not (root / row["case_id"] / "summary.csv").exists()
    ]
    if int(workers) <= 1 or len(tasks) <= 1:
        for row in tasks:
            _run_one_case(row, str(root), str(measured_params), str(prediction_model_path))
    else:
        with ProcessPoolExecutor(max_workers=int(workers)) as pool:
            futures = [
                pool.submit(_run_one_case, row, str(root), str(measured_params), str(prediction_model_path))
                for row in tasks
            ]
            for future in as_completed(futures):
                future.result()
    _write_summaries(root, manifest)
    _write_report(root, manifest)
    return root


def _run_one_case(row: dict[str, Any], root: str, measured_params: str, prediction_model_path: str) -> str:
    root_path = Path(root)
    raw_dir = EPLUS_ROOT / "out" / "energyplus_io_coupling_matrix_20260509" / row["case_id"]
    params_path = measured_params if row["controller"] == "io_coupled_measured_mpc" else DEFAULT_PARAM_YAML
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
        selected_output_root=root_path,
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
            "prediction_model_path": prediction_model_path if row["controller"] == "io_coupled_measured_mpc" else "",
            "control_surface": row["control_surface"],
            "matrix_days": int(row["days"]),
            "smoke": bool(row["smoke"]),
        },
    )
    return str(runner.run())


def _write_report(root: Path, manifest: pd.DataFrame) -> None:
    summary = pd.read_csv(root / "season_summary.csv") if (root / "season_summary.csv").exists() else pd.DataFrame()
    comparison = pd.read_csv(root / "comparison_summary.csv") if (root / "comparison_summary.csv").exists() else pd.DataFrame()
    DEFAULT_IO_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    DEFAULT_IO_REPORT_PATH.write_text(
        "\n".join(
            [
                "# EnergyPlus-MPC I/O Coupling Matrix Report 2026-05-09",
                "",
                "## Summary",
                "",
                f"- Result root: `{root}`",
                f"- Matrix cases expected: `{len(manifest)}`",
                f"- Matrix cases completed: `{len(summary)}`",
                "- Controllers: `no_mpc`, `tes_only_mpc`, `io_coupled_mpc`, `io_coupled_measured_mpc`",
                "- Control surface: `TES_Set` for TES-only MPC; `TES_Set,Chiller_T_Set` for I/O-coupled MPC.",
                "- `ITE_Set` remains an identification input and is not written by normal MPC controllers.",
                "- Parallel execution note: `--workers 8` can complete missing cases faster on this workstation, but one run produced EnergyPlus SQLite/runtime exceptions during concurrent startup. For formal reproduction, prefer `--workers 2` or smaller batches unless the machine is monitored.",
                "- Cost comparisons are valid as control-benefit evidence only when `cost_comparison_valid=true`.",
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
                "No thesis draft update is required until these results pass temperature-safety checks and are explicitly adopted as thesis conclusions.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", default=str(DEFAULT_IO_MATRIX_ROOT))
    parser.add_argument("--seasons", default="winter,spring,summer,autumn")
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--workers", type=int, default=1, help="Number of independent EnergyPlus cases to run in parallel.")
    parser.add_argument("--prediction-model", default=str(DEFAULT_PREDICTION_MODEL))
    parser.add_argument("--samples", default=str(DEFAULT_SAMPLES))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    seasons = [item.strip() for item in args.seasons.split(",") if item.strip()]
    unknown = [season for season in seasons if season not in SEASON_WINDOWS]
    if unknown:
        raise ValueError(f"unknown seasons: {unknown}")
    root = run_matrix(
        args.output_root,
        seasons,
        args.days,
        args.smoke,
        args.overwrite,
        max(1, int(args.workers)),
        args.prediction_model,
        args.samples,
    )
    print(root)
    print(DEFAULT_IO_REPORT_PATH)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
