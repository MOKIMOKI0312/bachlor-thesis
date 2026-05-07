"""Generate and optionally run the EnergyPlus MPC identification sampling matrix."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import pandas as pd

from .common import (
    DEFAULT_BASELINE_TIMESERIES,
    DEFAULT_EPLUS_INSTALL,
    DEFAULT_MODEL,
    DEFAULT_PARAM_YAML,
    DEFAULT_PRICE,
    DEFAULT_PV,
    DEFAULT_WEATHER,
    EPLUS_ROOT,
    REPO_ROOT,
)
from .run_energyplus_mpc import EnergyPlusMpcRunner


DEFAULT_SAMPLING_ROOT = REPO_ROOT / "results" / "energyplus_mpc_sampling_20260507"


def build_sampling_manifest(matrix: str = "high_explainable") -> pd.DataFrame:
    if matrix != "high_explainable":
        raise ValueError(f"unsupported sampling matrix: {matrix}")
    rows: list[dict[str, Any]] = [
        {
            "case_id": "baseline_reuse_ite045_chiller000_tes000",
            "family": "baseline_reuse",
            "purpose": "baseline_reference",
            "ite_set": 0.45,
            "chiller_t_set": 0.0,
            "tes_set": 0.0,
            "seed": "",
            "identification_only": False,
            "run_mode": "reuse_existing_baseline",
            "expected_raw_output_dir": str(EPLUS_ROOT / "out" / "energyplus_nanjing"),
        }
    ]
    for ite in [0.35, 0.45, 0.55]:
        for chiller_t in [0.0, 0.5, 1.0]:
            if ite == 0.45 and chiller_t == 0.0:
                continue
            rows.append(
                {
                    "case_id": f"plant_ite{_level(ite)}_chiller{_level(chiller_t)}",
                    "family": "plant_only",
                    "purpose": "plant_chiller_load_identification",
                    "ite_set": ite,
                    "chiller_t_set": chiller_t,
                    "tes_set": 0.0,
                    "seed": "",
                    "identification_only": True,
                    "run_mode": "energyplus_runtime",
                    "expected_raw_output_dir": str(EPLUS_ROOT / "out" / f"energyplus_sampling_plant_ite{_level(ite)}_chiller{_level(chiller_t)}"),
                }
            )
    for tes in [-1.0, -0.75, -0.5, -0.25, 0.25, 0.5, 0.75, 1.0]:
        sign = "neg" if tes < 0 else "pos"
        rows.append(
            {
                "case_id": f"tes_pulse_{sign}{abs(tes):.2f}".replace(".", "p"),
                "family": "tes_pulse",
                "purpose": "tes_source_use_soc_identification",
                "ite_set": 0.45,
                "chiller_t_set": 0.5,
                "tes_set": tes,
                "seed": "",
                "identification_only": True,
                "run_mode": "energyplus_runtime",
                "expected_raw_output_dir": str(EPLUS_ROOT / "out" / f"energyplus_sampling_tes_pulse_{sign}{abs(tes):.2f}".replace(".", "p")),
            }
        )
    for seed in range(6):
        rows.append(
            {
                "case_id": f"combined_seed_{seed}",
                "family": "combined",
                "purpose": "combined_interaction_validation",
                "ite_set": "",
                "chiller_t_set": "",
                "tes_set": "",
                "seed": seed,
                "identification_only": True,
                "run_mode": "energyplus_runtime",
                "expected_raw_output_dir": str(EPLUS_ROOT / "out" / f"energyplus_sampling_combined_seed_{seed}"),
            }
        )
    frame = pd.DataFrame(rows)
    if frame["case_id"].duplicated().any():
        duplicates = frame.loc[frame["case_id"].duplicated(), "case_id"].tolist()
        raise ValueError(f"duplicate sampling case ids: {duplicates}")
    return frame


def write_sampling_manifest(root: str | Path, matrix: str = "high_explainable") -> Path:
    output_root = Path(root)
    output_root.mkdir(parents=True, exist_ok=True)
    manifest = build_sampling_manifest(matrix)
    path = output_root / "sampling_manifest.csv"
    manifest.to_csv(path, index=False)
    return path


def run_sampling_matrix(args: argparse.Namespace) -> list[Path]:
    output_root = Path(args.output_root)
    manifest_path = write_sampling_manifest(output_root, args.matrix)
    manifest = pd.read_csv(manifest_path).fillna("")
    if args.dry_run:
        print(f"Sampling matrix dry-run manifest: {manifest_path}")
        print(f"cases: {len(manifest)} total, {(manifest['run_mode'] == 'energyplus_runtime').sum()} runnable")
        return []
    completed: list[Path] = []
    runnable = manifest[manifest["run_mode"] == "energyplus_runtime"]
    if args.case_limit is not None:
        runnable = runnable.head(args.case_limit)
    for row in runnable.to_dict("records"):
        case_id = str(row["case_id"])
        case_dir = output_root / case_id
        if case_dir.exists() and not args.overwrite:
            print(f"skip existing sampling case: {case_id}")
            completed.append(case_dir)
            continue
        profile = {k: row[k] for k in ["case_id", "family", "purpose", "identification_only", "seed"] if k in row}
        for key in ["ite_set", "chiller_t_set", "tes_set"]:
            if row.get(key) != "":
                profile[key] = float(row[key])
        runner = EnergyPlusMpcRunner(
            controller="sampling",
            max_steps=args.max_steps,
            eplus_root=args.energyplus_root,
            model=args.model,
            weather=args.weather,
            params_path=args.params,
            baseline_timeseries=args.baseline_timeseries,
            price_csv=args.price_csv,
            pv_csv=args.pv_csv,
            raw_output_dir=EPLUS_ROOT / "out" / f"energyplus_sampling_{case_id}",
            selected_output_root=output_root,
            record_start_step=args.record_start_step,
            sampling_profile=profile,
        )
        completed.append(runner.run())
        print(completed[-1])
    return completed


def _level(value: float) -> str:
    return f"{int(round(value * 100)):03d}"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix", default="high_explainable")
    parser.add_argument("--output-root", default=str(DEFAULT_SAMPLING_ROOT))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--max-steps", type=int, default=35040)
    parser.add_argument("--case-limit", type=int)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--record-start-step", default="0")
    parser.add_argument("--energyplus-root", default=str(DEFAULT_EPLUS_INSTALL))
    parser.add_argument("--model", default=str(DEFAULT_MODEL))
    parser.add_argument("--weather", default=str(DEFAULT_WEATHER))
    parser.add_argument("--params", default=str(DEFAULT_PARAM_YAML))
    parser.add_argument("--baseline-timeseries", default=str(DEFAULT_BASELINE_TIMESERIES))
    parser.add_argument("--price-csv", default=str(DEFAULT_PRICE))
    parser.add_argument("--pv-csv", default=str(DEFAULT_PV))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    run_sampling_matrix(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
