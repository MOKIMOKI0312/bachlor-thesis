"""Run the configured synthetic validation matrix for MPC v2."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from mpc_v2.core.io_schemas import load_yaml
from mpc_v2.scripts.run_closed_loop import run_closed_loop


def run_validation_matrix(
    config_path: str | Path = "mpc_v2/config/base.yaml",
    scenario_path: str | Path = "mpc_v2/config/scenario_sets.yaml",
    steps: int | None = None,
    output_root: str | Path | None = None,
) -> Path:
    """Run all configured synthetic scenarios and write a summary table."""

    scenarios = load_yaml(scenario_path)["scenarios"]
    root = Path(output_root or load_yaml(config_path)["paths"]["output_root"]) / "validation_matrix"
    root.mkdir(parents=True, exist_ok=True)
    rows = []
    for case_id, scenario in scenarios.items():
        run_dir = run_closed_loop(
            config_path=config_path,
            case_id=case_id,
            steps=steps,
            output_root=root,
            pv_perturbation=scenario.get("pv_perturbation", "nominal"),
            controller_mode=scenario.get("controller", "mpc"),
            tariff_multiplier=float(scenario.get("tariff_multiplier", 1.0)),
            outdoor_offset_C=float(scenario.get("outdoor_offset_C", 0.0)),
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
    parser.add_argument("--steps", type=int, default=None)
    parser.add_argument("--output-root", default=None)
    args = parser.parse_args()
    print(run_validation_matrix(args.config, args.scenarios, args.steps, args.output_root))


if __name__ == "__main__":
    main()

