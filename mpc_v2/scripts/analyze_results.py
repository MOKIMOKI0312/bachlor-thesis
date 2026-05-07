"""Aggregate validation runs and write paired comparison/statistics artifacts."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd

from mpc_v2.core.statistics import paired_metric_summary


def analyze_results(
    input_dir: str | Path,
    output_dir: str | Path | None = None,
    metric: str = "total_cost",
    baseline: str = "mpc_no_tes",
    candidate: str = "mpc",
) -> Path:
    """Read run summaries, write a combined summary and optional paired stats."""

    root = Path(input_dir)
    out = Path(output_dir) if output_dir is not None else root / "analysis"
    out.mkdir(parents=True, exist_ok=True)
    rows = _load_summary_rows(root)
    summary = pd.DataFrame(rows)
    summary.to_csv(out / "summary.csv", index=False)
    (out / "summary.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")

    stats_rows = []
    if not summary.empty and {"controller_type", metric}.issubset(summary.columns):
        summary = summary.copy()
        summary["pair_id"] = summary["scenario_id"].map(_default_pair_id)
        if baseline in set(summary["controller_type"]) and candidate in set(summary["controller_type"]):
            comparison = paired_metric_summary(
                summary,
                pair_columns=["pair_id"],
                controller_column="controller_type",
                metric=metric,
                baseline=baseline,
                candidate=candidate,
            )
            stats_rows.append(asdict(comparison))
    pd.DataFrame(stats_rows).to_csv(out / "paired_comparisons.csv", index=False)
    _write_optional_plots(summary, out)
    return out


def _load_summary_rows(root: Path) -> list[dict]:
    if (root / "validation_summary.csv").exists():
        return pd.read_csv(root / "validation_summary.csv").to_dict(orient="records")
    rows: list[dict] = []
    for path in sorted(root.rglob("episode_summary.json")):
        row = json.loads(path.read_text(encoding="utf-8"))
        row["run_dir"] = str(path.parent)
        rows.append(row)
    return rows


def _default_pair_id(scenario_id: str) -> str:
    value = str(scenario_id)
    for token in ["_mpc_no_tes", "_mpc_tes", "_mpc", "_no_tes", "_rbc_tes", "_direct_no_tes"]:
        value = value.replace(token, "")
    return value


def _write_optional_plots(summary: pd.DataFrame, output_dir: Path) -> None:
    try:
        import matplotlib.pyplot as plt
    except Exception:
        return
    if summary.empty:
        return
    if {"scenario_id", "total_cost"}.issubset(summary.columns):
        fig, ax = plt.subplots(figsize=(8, 4))
        summary.plot.bar(x="scenario_id", y="total_cost", ax=ax, legend=False)
        ax.set_ylabel("total_cost")
        ax.tick_params(axis="x", labelrotation=75)
        fig.tight_layout()
        fig.savefig(output_dir / "total_cost_by_scenario.png", dpi=160)
        plt.close(fig)
    if {"scenario_id", "solve_time_p95_s"}.issubset(summary.columns):
        fig, ax = plt.subplots(figsize=(8, 4))
        summary.plot.bar(x="scenario_id", y="solve_time_p95_s", ax=ax, legend=False)
        ax.set_ylabel("solve_time_p95_s")
        ax.tick_params(axis="x", labelrotation=75)
        fig.tight_layout()
        fig.savefig(output_dir / "solver_time_p95_by_scenario.png", dpi=160)
        plt.close(fig)
    _write_tou_curves(summary, output_dir, plt)
    _write_peakcap_tradeoff(summary, output_dir, plt)
    _write_dr_event_profile(summary, output_dir, plt)


def _write_tou_curves(summary: pd.DataFrame, output_dir: Path, plt) -> None:
    rows = []
    pattern = re.compile(
        r"^tou_screen_g(?P<gamma>[^_]+)_cp(?P<cp>[^_]+)_(?P<weather>hot|mild)_(?P<controller>.+)$"
    )
    for _, row in summary.iterrows():
        match = pattern.match(str(row.get("scenario_id", "")))
        if not match:
            continue
        item = row.to_dict()
        item.update(
            {
                "gamma_value": _token_float(match.group("gamma")),
                "cp_value": _token_float(match.group("cp")),
                "weather_case": match.group("weather"),
                "controller_label": match.group("controller"),
            }
        )
        rows.append(item)
    if not rows:
        return
    tou = pd.DataFrame(rows)
    _line_plot(
        tou,
        output_dir / "tou_cost_curve.png",
        plt,
        y_column="total_cost",
        y_label="Total cost",
        title="TOU screening cost response",
    )
    if "tes_arbitrage_price_spread" in tou.columns:
        _line_plot(
            tou,
            output_dir / "tou_arbitrage_spread_curve.png",
            plt,
            y_column="tes_arbitrage_price_spread",
            y_label="TES discharge-charge weighted price spread",
            title="TOU arbitrage price spread",
        )


def _line_plot(
    frame: pd.DataFrame,
    path: Path,
    plt,
    *,
    y_column: str,
    y_label: str,
    title: str,
) -> None:
    if y_column not in frame.columns:
        return
    fig, ax = plt.subplots(figsize=(8, 4.5))
    for (weather, cp, controller), group in frame.groupby(
        ["weather_case", "cp_value", "controller_label"]
    ):
        group = group.sort_values("gamma_value")
        label = f"{weather}, cp={cp:g}, {controller}"
        ax.plot(group["gamma_value"], group[y_column], marker="o", linewidth=1.6, label=label)
    ax.set_xlabel("TOU spread scaling gamma")
    ax.set_ylabel(y_label)
    ax.set_title(title)
    ax.grid(True, alpha=0.25)
    ax.legend(fontsize=7, ncol=2)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def _write_peakcap_tradeoff(summary: pd.DataFrame, output_dir: Path, plt) -> None:
    rows = []
    pattern = re.compile(
        r"^peakcap_r(?P<ratio>[^_]+)_eta(?P<eta>[^_]+)_(?P<controller>.+)$"
    )
    for _, row in summary.iterrows():
        match = pattern.match(str(row.get("scenario_id", "")))
        if not match:
            continue
        item = row.to_dict()
        item.update(
            {
                "cap_ratio": _token_float(match.group("ratio")),
                "eta_value": _token_float(match.group("eta")),
                "controller_label": match.group("controller"),
            }
        )
        rows.append(item)
    if not rows or not {"peak_grid_kw", "total_cost"}.issubset(summary.columns):
        return
    peakcap = pd.DataFrame(rows)
    fig, ax = plt.subplots(figsize=(7, 4.5))
    for (controller, eta), group in peakcap.groupby(["controller_label", "eta_value"]):
        group = group.sort_values("cap_ratio", ascending=False)
        ax.plot(
            group["peak_grid_kw"],
            group["total_cost"],
            marker="o",
            linewidth=1.5,
            label=f"{controller}, eta={eta:g}",
        )
    ax.set_xlabel("Achieved peak grid import (kW)")
    ax.set_ylabel("Total cost")
    ax.set_title("Peak-cap reduction-cost tradeoff")
    ax.grid(True, alpha=0.25)
    ax.legend(fontsize=7, ncol=2)
    fig.tight_layout()
    fig.savefig(output_dir / "peak_reduction_cost_tradeoff.png", dpi=160)
    plt.close(fig)


def _write_dr_event_profile(summary: pd.DataFrame, output_dir: Path, plt) -> None:
    if "run_dir" not in summary.columns:
        return
    candidates = summary[
        summary["scenario_id"].astype(str).str.startswith("dr_")
        & summary["controller_type"].astype(str).eq("mpc")
    ]
    if candidates.empty:
        candidates = summary[summary["scenario_id"].astype(str).str.startswith("dr_")]
    for _, row in candidates.iterrows():
        run_dir = Path(str(row["run_dir"]))
        monitor_path = run_dir / "monitor.csv"
        if not monitor_path.exists():
            continue
        monitor = pd.read_csv(monitor_path)
        if "dr_flag" not in monitor.columns or monitor["dr_flag"].fillna(0).sum() <= 0:
            continue
        event_idx = monitor.index[monitor["dr_flag"].fillna(0) > 0].tolist()
        start = max(min(event_idx) - 12, 0)
        end = min(max(event_idx) + 13, len(monitor))
        profile = monitor.iloc[start:end].copy()
        x = pd.to_datetime(profile["timestamp"]) if "timestamp" in profile.columns else profile.index
        fig, ax = plt.subplots(figsize=(8, 4.5))
        if "grid_import_kw" in profile.columns:
            ax.plot(x, profile["grid_import_kw"], label="grid import", linewidth=1.8)
        if "dr_baseline_kw" in profile.columns:
            ax.plot(x, profile["dr_baseline_kw"], label="DR baseline", linestyle="--")
        if {"dr_baseline_kw", "dr_req_kw"}.issubset(profile.columns):
            ax.plot(
                x,
                profile["dr_baseline_kw"] - profile["dr_req_kw"],
                label="DR target",
                linestyle=":",
            )
        if "dr_flag" in profile.columns:
            active = profile["dr_flag"].fillna(0) > 0
            if active.any():
                ax.fill_between(
                    x,
                    ax.get_ylim()[0],
                    ax.get_ylim()[1],
                    where=active,
                    color="tab:orange",
                    alpha=0.12,
                    label="DR event",
                )
        ax.set_xlabel("Timestamp")
        ax.set_ylabel("kW")
        ax.set_title(f"DR event profile: {row['scenario_id']}")
        ax.grid(True, alpha=0.25)
        ax.legend(fontsize=8)
        fig.autofmt_xdate()
        fig.tight_layout()
        fig.savefig(output_dir / "dr_event_profile.png", dpi=160)
        plt.close(fig)
        return


def _token_float(value: str) -> float:
    return float(str(value).replace("p", "."))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", required=True)
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--metric", default="total_cost")
    parser.add_argument("--baseline", default="mpc_no_tes")
    parser.add_argument("--candidate", default="mpc")
    args = parser.parse_args()
    print(
        analyze_results(
            input_dir=args.input_dir,
            output_dir=args.output_dir,
            metric=args.metric,
            baseline=args.baseline,
            candidate=args.candidate,
        )
    )


if __name__ == "__main__":
    main()
