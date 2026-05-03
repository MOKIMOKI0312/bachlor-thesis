from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


GAUSS_CELL_IDS = {
    ("05", 1): 2,
    ("05", 2): 3,
    ("05", 3): 4,
    ("10", 1): 5,
    ("10", 2): 6,
    ("10", 3): 7,
    ("20", 1): 8,
    ("20", 2): 9,
    ("20", 3): 10,
}
PERSIST_CELL_IDS = {
    1: 11,
    4: 12,
    12: 13,
}
REQUIRED_RESULT_KEYS = [
    "solver_used",
    "solver_status",
    "forecast_noise_mode",
    "forecast_noise_sigma",
    "forecast_noise_seed",
    "forecast_noise_persist_h",
    "mechanism_gate_pass",
    "charge_window_sign_rate",
    "delta_soc_prepeak",
    "delta_soc_peak",
    "pue",
    "cost_usd",
]


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs-dir", type=Path, required=True)
    ap.add_argument("--ts", required=True)
    return ap.parse_args()


def _require_result_keys(result: dict[str, Any], path: Path) -> None:
    missing = [key for key in REQUIRED_RESULT_KEYS if key not in result]
    if missing:
        raise RuntimeError(f"Missing keys in {path}: {missing}")


def _mode_switches(monitor_path: Path) -> int:
    df = pd.read_csv(monitor_path)
    if "tes_mpc_mode_label" not in df.columns:
        raise RuntimeError(f"Missing tes_mpc_mode_label in {monitor_path}")
    labels = df["tes_mpc_mode_label"].fillna("").astype(str).to_numpy()
    if len(labels) <= 1:
        return 0
    return int(np.sum(labels[1:] != labels[:-1]))


def _parse_tag(tag: str, ts: str) -> tuple[int, str, float | None, int, int | None]:
    if tag == f"w1_3_perfect_{ts}":
        return 1, "perfect", None, 0, None

    match = re.fullmatch(rf"w1_3_gauss_s(05|10|20)_seed([123])_{re.escape(ts)}", tag)
    if match:
        slabel = match.group(1)
        seed = int(match.group(2))
        sigma = {"05": 0.05, "10": 0.10, "20": 0.20}[slabel]
        return GAUSS_CELL_IDS[(slabel, seed)], "gaussian", sigma, seed, None

    match = re.fullmatch(rf"w1_3_persist_h(1|4|12)_{re.escape(ts)}", tag)
    if match:
        persist_h = int(match.group(1))
        return PERSIST_CELL_IDS[persist_h], "persistence_h", None, 0, persist_h

    raise RuntimeError(f"Unexpected tag format for ts={ts}: {tag}")


def main() -> None:
    args = parse_args()
    run_dirs = sorted(args.runs_dir.glob(f"w1_3_*_{args.ts}"))
    if len(run_dirs) != 13:
        raise RuntimeError(f"Expected 13 run directories for ts={args.ts}, found {len(run_dirs)}")

    rows: list[dict[str, Any]] = []
    for run_dir in run_dirs:
        result_path = run_dir / "result.json"
        monitor_path = run_dir / "monitor.csv"
        if not result_path.exists() or not monitor_path.exists():
            raise RuntimeError(f"Missing result.json or monitor.csv under {run_dir}")
        result = json.loads(result_path.read_text(encoding="utf-8"))
        _require_result_keys(result, result_path)
        tag = str(result["tag"])
        cell_id, noise_mode, sigma, seed, persist_h = _parse_tag(tag, args.ts)
        rows.append(
            {
                "cell_id": cell_id,
                "tag": tag,
                "noise_mode": noise_mode,
                "sigma": sigma,
                "seed": seed,
                "persist_h": persist_h,
                "sign_rate": result["charge_window_sign_rate"],
                "dsoc_prepeak": result["delta_soc_prepeak"],
                "dsoc_peak": result["delta_soc_peak"],
                "pue": result["pue"],
                "cost_usd": result["cost_usd"],
                "mode_switches": _mode_switches(monitor_path),
                "mechanism_gate_pass": result["mechanism_gate_pass"],
                "solver_status": result["solver_status"],
            }
        )

    df = pd.DataFrame(rows).sort_values("cell_id").reset_index(drop=True)
    csv_path = Path("analysis") / f"m2f1_w1_3_robustness_curve_{args.ts}.csv"
    md_path = Path("analysis") / f"m2f1_w1_3_robustness_curve_{args.ts}.md"
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(csv_path, index=False)

    display_df = df.copy()
    display_df["sigma"] = display_df["sigma"].map(lambda x: "" if pd.isna(x) else f"{float(x):.2f}")
    display_df["persist_h"] = display_df["persist_h"].map(lambda x: "" if pd.isna(x) else str(int(x)))
    display_df["sign_rate"] = display_df["sign_rate"].map(lambda x: "" if pd.isna(x) else f"{float(x):.4f}")
    display_df["dsoc_prepeak"] = display_df["dsoc_prepeak"].map(lambda x: "" if pd.isna(x) else f"{float(x):+.4f}")
    display_df["dsoc_peak"] = display_df["dsoc_peak"].map(lambda x: "" if pd.isna(x) else f"{float(x):+.4f}")
    display_df["pue"] = display_df["pue"].map(lambda x: "" if pd.isna(x) else f"{float(x):.5f}")
    display_df["cost_usd"] = display_df["cost_usd"].map(lambda x: "" if pd.isna(x) else f"{float(x):.2f}")
    display_df["mechanism_gate_pass"] = display_df["mechanism_gate_pass"].map(lambda x: "true" if bool(x) else "false")

    md_lines = [
        f"# W1-3 Robustness Curve ({args.ts})",
        "",
        display_df.to_markdown(index=False),
        "",
    ]
    md_path.write_text("\n".join(md_lines), encoding="utf-8")
    print(csv_path)
    print(md_path)


if __name__ == "__main__":
    main()
