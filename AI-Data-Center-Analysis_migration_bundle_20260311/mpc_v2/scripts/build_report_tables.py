"""Build compact Markdown/CSV report tables from MPC v2 summaries."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


def build_report_tables(input_path: str | Path, output_dir: str | Path | None = None) -> Path:
    """Convert one summary JSON or validation summary JSON into report tables."""

    input_path = Path(input_path)
    output = Path(output_dir or input_path.parent)
    output.mkdir(parents=True, exist_ok=True)
    data = json.loads(input_path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        rows = [data]
    else:
        rows = list(data)
    frame = pd.DataFrame(rows)
    csv_path = output / "report_table.csv"
    md_path = output / "report_table.md"
    frame.to_csv(csv_path, index=False)
    md_path.write_text(frame.to_markdown(index=False), encoding="utf-8")
    return md_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_path")
    parser.add_argument("--output-dir", default=None)
    args = parser.parse_args()
    print(build_report_tables(args.input_path, args.output_dir))


if __name__ == "__main__":
    main()

