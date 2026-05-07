"""Collect rebuilt MPC v1 summary.csv files into one table."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd


def collect_summaries(root: str | Path) -> pd.DataFrame:
    rows = []
    for path in Path(root).rglob("summary.csv"):
        frame = pd.read_csv(path)
        if not frame.empty:
            row = frame.iloc[0].to_dict()
            row["summary_path"] = str(path)
            rows.append(row)
    return pd.DataFrame(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root")
    parser.add_argument("--output")
    args = parser.parse_args(argv)
    frame = collect_summaries(args.root)
    if args.output:
        frame.to_csv(args.output, index=False)
    else:
        print(frame.to_csv(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
