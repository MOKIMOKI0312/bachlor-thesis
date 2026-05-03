"""M2-F1 supervisory MPC-lite evaluation.

The heuristic mode is a controller-shaped baseline, not an optimization MPC.
The scipy-highs mode runs the TES-only rolling LP implemented in the shared
oracle module and fails loudly if the optimizer stack is unavailable.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.m2_tes_mpc_oracle import add_common_args, evaluate_controller


def parse_args() -> argparse.Namespace:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    ap = argparse.ArgumentParser()
    add_common_args(ap)
    ap.set_defaults(tag=f"m2f1_mpc_lite_{stamp}", out_dir=Path("runs/m2_mpc_lite"))
    ap.add_argument("--solver", default="heuristic", choices=["heuristic", "scipy-highs"])
    ap.add_argument("--switch-penalty", type=float, default=0.0)
    ap.add_argument("--terminal-soc-weight", type=float, default=1.0)
    args = ap.parse_args()
    args.controller_type = "mpc_lite"
    args.controller_family = "mpc_lite"
    if args.solver == "heuristic":
        args.controller_type_detail = "mpc_lite_heuristic"
        args.solver_used = "heuristic"
        args.solver_status = "heuristic baseline; not an optimization MPC"
    else:
        args.controller_type_detail = "mpc_lite_optimizer_scipy_highs_tes_only"
        args.solver_used = "scipy-highs"
        args.solver_status = "requested scipy-highs rolling LP optimizer"
    return args


def main() -> None:
    args = parse_args()
    result = evaluate_controller(args)
    print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False))
    print(f"Wrote {Path(args.out_dir) / args.tag / 'result.json'}")
    print(f"Wrote {Path(args.out_dir) / args.tag / 'monitor.csv'}")


if __name__ == "__main__":
    main()
