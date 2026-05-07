"""Run one Kim-lite paper-like controller case."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from mpc_v2.kim_lite.config import load_config
from mpc_v2.kim_lite.controller import run_controller_case
from mpc_v2.kim_lite.model import build_inputs


def run_kim_lite_closed_loop(
    config_path: str = "mpc_v2/config/kim_lite_base.yaml",
    controller: str = "paper_like_mpc",
    case_id: str = "kim_lite_case",
    steps: int | None = None,
    output_root: str | None = None,
    tariff_gamma: float = 1.0,
    cp_uplift: float = 0.0,
    peak_cap_kw: float | None = None,
    enforce_signed_ramp: bool = False,
) -> Path:
    cfg = load_config(config_path)
    n_steps = int(steps or cfg.default_steps)
    inputs = build_inputs(cfg, n_steps, tariff_gamma=tariff_gamma, cp_uplift=cp_uplift)
    run_dir, _ = run_controller_case(
        cfg,
        inputs,
        controller=controller,
        case_id=case_id,
        output_root=output_root or cfg.output_root,
        peak_cap_kw=peak_cap_kw,
        enforce_signed_ramp=enforce_signed_ramp,
    )
    return run_dir


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="mpc_v2/config/kim_lite_base.yaml")
    parser.add_argument("--controller", default="paper_like_mpc")
    parser.add_argument("--case-id", default="kim_lite_case")
    parser.add_argument("--steps", type=int)
    parser.add_argument("--output-root")
    parser.add_argument("--tariff-gamma", type=float, default=1.0)
    parser.add_argument("--cp-uplift", type=float, default=0.0)
    parser.add_argument("--peak-cap-kw", type=float)
    parser.add_argument("--enforce-signed-ramp", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    run_dir = run_kim_lite_closed_loop(
        config_path=args.config,
        controller=args.controller,
        case_id=args.case_id,
        steps=args.steps,
        output_root=args.output_root,
        tariff_gamma=args.tariff_gamma,
        cp_uplift=args.cp_uplift,
        peak_cap_kw=args.peak_cap_kw,
        enforce_signed_ramp=args.enforce_signed_ramp,
    )
    print(run_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
