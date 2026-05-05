"""Run configured closed-loop validation scenarios."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from mpc_v2.core.io_schemas import load_yaml
from mpc_v2.scripts.run_closed_loop import run_closed_loop


def run_validation_matrix(
    config_path: str | Path = "mpc_v2/config/base.yaml",
    scenario_path: str | Path = "mpc_v2/config/scenario_sets.yaml",
    scenario_set: str = "thesis_core",
    steps: int | None = None,
    output_dir: str | Path = "runs/final_mpc_validation",
) -> Path:
    """Run each scenario in a named set and write a summary table."""

    scenario_cfg = load_yaml(scenario_path)
    scenario_names = scenario_cfg["scenario_sets"][scenario_set]
    scenarios = scenario_cfg["scenarios"]
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    rows = []
    for scenario_id in scenario_names:
        scenario = scenarios[scenario_id]
        run_dir = run_closed_loop(
            config_path=config_path,
            case_id=scenario_id,
            steps=steps,
            output_root=root,
            pv_error_sigma=float(scenario.get("pv_error_sigma", 0.0)),
            controller_mode=str(scenario.get("controller_type", "mpc")),
            tariff_multiplier=float(scenario.get("tariff_multiplier", 1.0)),
            outdoor_offset_c=float(scenario.get("outdoor_offset_c", 0.0)),
            pv_scale=float(scenario.get("pv_scale", 1.0)),
            demand_charge_rate=(
                float(scenario["demand_charge_currency_per_kw_day"])
                if "demand_charge_currency_per_kw_day" in scenario
                else None
            ),
            demand_charge_multiplier=float(scenario.get("demand_charge_multiplier", 1.0)),
        )
        summary = json.loads((run_dir / "episode_summary.json").read_text(encoding="utf-8"))
        summary["run_dir"] = str(run_dir)
        rows.append(summary)
    frame = pd.DataFrame(rows)
    frame.to_csv(root / "validation_summary.csv", index=False)
    (root / "validation_summary.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    return root


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="mpc_v2/config/base.yaml")
    parser.add_argument("--scenarios", default="mpc_v2/config/scenario_sets.yaml")
    parser.add_argument("--scenario-set", default="thesis_core")
    parser.add_argument("--steps", type=int, default=None)
    parser.add_argument("--output-dir", default="runs/final_mpc_validation")
    args = parser.parse_args()
    print(
        run_validation_matrix(
            config_path=args.config,
            scenario_path=args.scenarios,
            scenario_set=args.scenario_set,
            steps=args.steps,
            output_dir=args.output_dir,
        )
    )


if __name__ == "__main__":
    main()
