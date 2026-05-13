"""Generate Phase 3 PV-TES technical sizing plots."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from mpc_v2.phase3_sizing.plotting import generate_phase3_plots


def plot_phase3_results(summary_path: str | Path, output_dir: str | Path) -> list[Path]:
    summary = pd.read_csv(summary_path)
    return generate_phase3_plots(summary, output_dir)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    for path in plot_phase3_results(args.summary, args.output_dir):
        print(path)


if __name__ == "__main__":
    main()
