"""Run a small rebuilt MPC validation matrix."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd
import yaml

from mpc_v2.scripts.run_closed_loop import run_closed_loop


def run_validation_matrix(
    matrix_path: str | Path = "mpc_v2/config/scenario_sets.yaml",
    output_root: str | Path | None = None,
    config_path: str | Path = "mpc_v2/config/base.yaml",
) -> Path:
    """Run all scenarios listed in a minimal matrix YAML."""

    matrix = _load_matrix(matrix_path)
    root = Path(output_root or matrix.get("output_root", "runs/mpc_v2_matrix"))
    root.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    for scenario in matrix["scenarios"]:
        case_id = str(scenario["case_id"])
        run_dir = run_closed_loop(
            config_path=scenario.get("config_path", config_path),
            case_id=case_id,
            steps=int(scenario.get("steps", matrix.get("steps", 96))),
            output_root=root,
            controller_mode=str(scenario.get("controller_mode", "mpc")),
            horizon_steps_override=scenario.get("horizon_steps", matrix.get("horizon_steps")),
            initial_soc=scenario.get("initial_soc"),
            soc_target=scenario.get("soc_target"),
            pv_scale=scenario.get("pv_scale"),
            tariff_multiplier=float(scenario.get("tariff_multiplier", 1.0)),
            truncate_horizon_to_episode=bool(scenario.get("truncate_horizon_to_episode", False)),
        )
        summary = json.loads((run_dir / "episode_summary.json").read_text(encoding="utf-8"))
        rows.append({"case_id": case_id, "run_dir": str(run_dir), **summary})
    frame = pd.DataFrame(rows)
    frame.to_csv(root / "validation_summary.csv", index=False)
    (root / "validation_summary.json").write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    return root


def _load_matrix(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as fh:
        matrix = yaml.safe_load(fh)
    if not isinstance(matrix, dict) or not isinstance(matrix.get("scenarios"), list):
        raise ValueError(f"matrix must contain a scenarios list: {path}")
    for scenario in matrix["scenarios"]:
        if "case_id" not in scenario:
            raise ValueError("each scenario must define case_id")
    return matrix


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix", default="mpc_v2/config/scenario_sets.yaml")
    parser.add_argument("--output-root")
    parser.add_argument("--config", default="mpc_v2/config/base.yaml")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    output = run_validation_matrix(args.matrix, args.output_root, args.config)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
