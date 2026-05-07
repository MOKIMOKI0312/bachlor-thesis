"""Regenerate Kim-lite figures from existing run outputs."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from mpc_v2.kim_lite.plotting import plot_representative_dispatch, plot_summary_bar, plot_xy


def plot_all(root: str | Path = "results/kim_lite_repro_20260507") -> Path:
    root = Path(root)
    fig_dir = root / "figures"
    if (root / "phase_a" / "paper_like_mpc" / "monitor.csv").exists():
        plot_representative_dispatch(
            root / "phase_a" / "paper_like_mpc" / "monitor.csv",
            fig_dir / "fig_phase_a_dispatch.png",
            "Phase A paper-like MPC dispatch",
        )
    if (root / "phase_b_attribution" / "summary.csv").exists():
        plot_summary_bar(
            root / "phase_b_attribution" / "summary.csv",
            fig_dir / "fig_phase_b_cost_by_controller.png",
            "controller",
            "cost_total",
            "Phase B controller cost",
        )
    if (root / "phase_c_tou" / "summary.csv").exists():
        plot_xy(root / "phase_c_tou" / "summary.csv", fig_dir / "fig_tou_cost_vs_gamma.png", "spread_gamma", "cost_total", "TOU cost vs gamma")
        plot_xy(
            root / "phase_c_tou" / "summary.csv",
            fig_dir / "fig_tou_arbitrage_spread_vs_gamma.png",
            "spread_gamma",
            "TES_arbitrage_spread",
            "TOU arbitrage spread vs gamma",
        )
    if (root / "phase_d_peakcap" / "summary.csv").exists():
        plot_xy(
            root / "phase_d_peakcap" / "summary.csv",
            fig_dir / "fig_peak_reduction_cost_tradeoff.png",
            "peak_reduction_kw",
            "cost_increase_vs_no_cap",
            "Peak reduction cost tradeoff",
        )
    return fig_dir


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default="results/kim_lite_repro_20260507")
    args = parser.parse_args(argv)
    print(plot_all(args.root))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
