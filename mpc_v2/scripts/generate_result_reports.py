"""Generate per-case plots/reports and an aggregate report for matrix results."""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd


MATLAB_COLORS = [
    "#0072BD",
    "#D95319",
    "#EDB120",
    "#7E2F8E",
    "#77AC30",
    "#4DBEEE",
    "#A2142F",
]


def generate_result_reports(
    result_dir: str | Path = "results/china_tou_dr_matrices_20260506",
    output_dir: str | Path | None = None,
) -> Path:
    """Generate four MATLAB-style figures and one report for every run."""

    root = Path(result_dir)
    out = Path(output_dir) if output_dir is not None else root / "reports"
    cases_dir = out / "cases"
    cases_dir.mkdir(parents=True, exist_ok=True)
    _set_matlab_style()

    summary = pd.read_csv(root / "validation_summary.csv")
    summary = summary.sort_values("scenario_id").reset_index(drop=True)
    pair_context = _build_pair_context(summary)
    index_rows: list[dict[str, Any]] = []

    for _, row in summary.iterrows():
        scenario_id = str(row["scenario_id"])
        case_dir = cases_dir / scenario_id
        case_dir.mkdir(parents=True, exist_ok=True)
        run_dir = _resolve_run_dir(root, row)
        monitor = pd.read_csv(run_dir / "monitor.csv")
        solver = _read_optional_csv(run_dir / "solver_log.csv")
        events = _read_optional_csv(run_dir / "events.csv")
        figures = _write_case_figures(case_dir, scenario_id, monitor, solver)
        notes = _case_notes(row, pair_context.get(scenario_id), events)
        report_path = case_dir / "report.md"
        report_path.write_text(
            _case_report_markdown(row, run_dir, figures, notes, events),
            encoding="utf-8",
        )
        index_rows.append(
            {
                "scenario_id": scenario_id,
                "controller_type": row.get("controller_type"),
                "category": _category(scenario_id),
                "report": str(report_path.relative_to(out)).replace("\\", "/"),
                "total_cost": row.get("total_cost"),
                "peak_grid_kw": row.get("peak_grid_kw"),
                "temp_violation_degree_hours": row.get("temp_violation_degree_hours"),
                "fallback_count": row.get("fallback_count"),
            }
        )

    index = pd.DataFrame(index_rows)
    index.to_csv(out / "case_index.csv", index=False)
    (out / "summary_report.md").write_text(
        _summary_report_markdown(root, out, summary, index),
        encoding="utf-8",
    )
    return out


def _set_matlab_style() -> None:
    plt.rcParams.update(
        {
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "axes.edgecolor": "black",
            "axes.grid": True,
            "grid.color": "#D0D0D0",
            "grid.linestyle": "-",
            "grid.linewidth": 0.6,
            "axes.prop_cycle": plt.cycler(color=MATLAB_COLORS),
            "font.size": 9,
            "axes.titlesize": 11,
            "axes.labelsize": 9,
            "legend.fontsize": 8,
            "lines.linewidth": 1.35,
            "savefig.dpi": 130,
        }
    )


def _resolve_run_dir(root: Path, row: pd.Series) -> Path:
    leaf = Path(str(row["run_dir"])).name
    frozen = root / "raw" / leaf
    if frozen.exists():
        return frozen
    source = Path(str(row["run_dir"]))
    if source.exists():
        return source
    raise FileNotFoundError(f"cannot resolve run directory for {row['scenario_id']}")


def _read_optional_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path) if path.exists() else pd.DataFrame()


def _write_case_figures(
    case_dir: Path,
    scenario_id: str,
    monitor: pd.DataFrame,
    solver: pd.DataFrame,
) -> list[str]:
    time = pd.to_datetime(monitor["timestamp"])
    figures = [
        _plot_power(case_dir, scenario_id, time, monitor),
        _plot_tes_soc(case_dir, scenario_id, time, monitor),
        _plot_temperature(case_dir, scenario_id, time, monitor),
        _plot_tariff_solver(case_dir, scenario_id, time, monitor, solver),
    ]
    return [name for name in figures if name]


def _plot_power(case_dir: Path, scenario_id: str, time: pd.Series, m: pd.DataFrame) -> str:
    name = "01_power_grid_pv.png"
    fig, ax = plt.subplots(figsize=(8.4, 4.8))
    _plot_if_exists(ax, time, m, "grid_import_kw", "Grid import")
    _plot_if_exists(ax, time, m, "facility_power_kw", "Facility power")
    _plot_if_exists(ax, time, m, "pv_actual_kw", "PV actual")
    if "peak_cap_kw" in m.columns:
        cap = pd.to_numeric(m["peak_cap_kw"], errors="coerce")
        if cap.notna().any() and (cap > 0).any():
            ax.plot(time, cap, "--", label="Peak cap")
    if {"dr_baseline_kw", "dr_req_kw", "dr_flag"}.issubset(m.columns):
        active = m["dr_flag"].fillna(0) > 0
        if active.any():
            target = m["dr_baseline_kw"] - m["dr_req_kw"]
            ax.plot(time, target, ":", label="DR target")
            _shade_active(ax, time, active, "DR event")
    ax.set_title(f"{scenario_id}: grid/PV/power")
    ax.set_xlabel("Time")
    ax.set_ylabel("Power (kW)")
    ax.legend(loc="best")
    _finish_time_axis(fig, ax)
    fig.savefig(case_dir / name, bbox_inches="tight")
    plt.close(fig)
    return name


def _plot_tes_soc(case_dir: Path, scenario_id: str, time: pd.Series, m: pd.DataFrame) -> str:
    name = "02_tes_soc_operation.png"
    fig, ax = plt.subplots(figsize=(8.4, 4.8))
    _plot_if_exists(ax, time, m, "q_ch_tes_kw_th", "TES charge")
    if "q_dis_tes_kw_th" in m.columns:
        ax.plot(time, -pd.to_numeric(m["q_dis_tes_kw_th"], errors="coerce"), label="-TES discharge")
    ax.set_xlabel("Time")
    ax.set_ylabel("TES power (kW_th)")
    ax2 = ax.twinx()
    if "soc" in m.columns:
        ax2.plot(time, m["soc"], color=MATLAB_COLORS[3], label="SOC", linewidth=1.6)
        ax2.set_ylabel("SOC")
        ax2.set_ylim(0, 1)
    lines, labels = _combined_legend(ax, ax2)
    ax.legend(lines, labels, loc="best")
    ax.set_title(f"{scenario_id}: TES operation and SOC")
    _finish_time_axis(fig, ax)
    fig.savefig(case_dir / name, bbox_inches="tight")
    plt.close(fig)
    return name


def _plot_temperature(case_dir: Path, scenario_id: str, time: pd.Series, m: pd.DataFrame) -> str:
    name = "03_temperature_constraints.png"
    fig, ax = plt.subplots(figsize=(8.4, 4.8))
    _plot_if_exists(ax, time, m, "room_temp_c", "Room temp")
    _plot_if_exists(ax, time, m, "outdoor_temp_c", "Outdoor temp")
    ax.axhline(27.0, color=MATLAB_COLORS[6], linestyle="--", label="Temp max 27C")
    ax.axhline(23.5, color=MATLAB_COLORS[4], linestyle="--", label="Temp min 23.5C")
    ax.set_title(f"{scenario_id}: temperature constraints")
    ax.set_xlabel("Time")
    ax.set_ylabel("Temperature (C)")
    ax.legend(loc="best")
    _finish_time_axis(fig, ax)
    fig.savefig(case_dir / name, bbox_inches="tight")
    plt.close(fig)
    return name


def _plot_tariff_solver(
    case_dir: Path,
    scenario_id: str,
    time: pd.Series,
    m: pd.DataFrame,
    solver: pd.DataFrame,
) -> str:
    name = "04_tariff_solver_flags.png"
    fig, ax = plt.subplots(figsize=(8.4, 4.8))
    price_col = "price_total_cny_mwh" if "price_total_cny_mwh" in m.columns else "price_currency_per_mwh"
    _plot_if_exists(ax, time, m, price_col, "Price")
    if "cp_flag" in m.columns and m["cp_flag"].fillna(0).sum() > 0:
        _shade_active(ax, time, m["cp_flag"].fillna(0) > 0, "Critical peak")
    if "fallback_used" in m.columns and m["fallback_used"].fillna(0).sum() > 0:
        _shade_active(ax, time, m["fallback_used"].fillna(0) > 0, "Fallback")
    ax.set_xlabel("Time")
    ax.set_ylabel("Price (CNY/MWh)")
    ax2 = ax.twinx()
    if not solver.empty and "solve_time_s" in solver.columns:
        stime = pd.to_datetime(solver["timestamp"]) if "timestamp" in solver.columns else time.iloc[: len(solver)]
        ax2.plot(stime, solver["solve_time_s"], color=MATLAB_COLORS[1], alpha=0.65, label="Solve time")
        ax2.set_ylabel("Solve time (s)")
    lines, labels = _combined_legend(ax, ax2)
    ax.legend(lines, labels, loc="best")
    ax.set_title(f"{scenario_id}: tariff and solver trace")
    _finish_time_axis(fig, ax)
    fig.savefig(case_dir / name, bbox_inches="tight")
    plt.close(fig)
    return name


def _plot_if_exists(ax, time: pd.Series, frame: pd.DataFrame, column: str, label: str) -> None:
    if column in frame.columns:
        ax.plot(time, pd.to_numeric(frame[column], errors="coerce"), label=label)


def _shade_active(ax, time: pd.Series, active: pd.Series, label: str) -> None:
    y0, y1 = ax.get_ylim()
    ax.fill_between(time, y0, y1, where=active.to_numpy(), alpha=0.12, label=label)
    ax.set_ylim(y0, y1)


def _combined_legend(ax, ax2) -> tuple[list[Any], list[str]]:
    lines1, labels1 = ax.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    return lines1 + lines2, labels1 + labels2


def _finish_time_axis(fig, ax) -> None:
    ax.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=4, maxticks=8))
    ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(ax.xaxis.get_major_locator()))
    ax.grid(True)
    fig.autofmt_xdate()


def _build_pair_context(summary: pd.DataFrame) -> dict[str, dict[str, Any]]:
    context: dict[str, dict[str, Any]] = {}
    frame = summary.copy()
    frame["pair_id"] = frame["scenario_id"].map(_pair_id)
    for _, group in frame.groupby("pair_id"):
        if {"mpc", "mpc_no_tes"}.issubset(set(group["controller_type"].astype(str))):
            base = group[group["controller_type"].astype(str) == "mpc_no_tes"].iloc[0]
            cand = group[group["controller_type"].astype(str) == "mpc"].iloc[0]
            delta = float(base["total_cost"] - cand["total_cost"])
            context[str(base["scenario_id"])] = {
                "paired_with": str(cand["scenario_id"]),
                "tes_incremental_saving_cny": delta,
                "role": "baseline_mpc_no_tes",
            }
            context[str(cand["scenario_id"])] = {
                "paired_with": str(base["scenario_id"]),
                "tes_incremental_saving_cny": delta,
                "role": "tes_mpc",
            }
    return context


def _pair_id(scenario_id: str) -> str:
    value = str(scenario_id)
    for token in ["_mpc_no_tes", "_mpc_tes", "_mpc", "_no_tes", "_rbc_tes", "_direct_no_tes"]:
        value = value.replace(token, "")
    return value


def _case_notes(row: pd.Series, pair: dict[str, Any] | None, events: pd.DataFrame) -> list[str]:
    notes: list[str] = []
    cost = _fmt(row.get("total_cost"), 2)
    notes.append(f"该 case 的月总成本为 {cost} CNY，峰值购电为 {_fmt(row.get('peak_grid_kw'), 2)} kW。")
    temp = float(row.get("temp_violation_degree_hours", 0.0) or 0.0)
    if temp > 1e-6:
        notes.append(f"存在温度约束压力：温度违约为 {_fmt(temp, 3)} degree-hours，最高温度 {_fmt(row.get('max_temp_c'), 3)} C。")
    else:
        notes.append("温度违约为 0，当前代理模型下满足温度约束。")
    fallback = int(row.get("fallback_count", 0) or 0)
    if fallback:
        notes.append(f"该 case 出现 {fallback} 次 fallback；可行率为 {_fmt(row.get('feasible_rate'), 6)}。")
    else:
        notes.append("求解过程中未触发 fallback。")
    if pair:
        delta = float(pair["tes_incremental_saving_cny"])
        direction = "节省" if delta >= 0 else "增加成本"
        notes.append(
            f"与配对场景 `{pair['paired_with']}` 相比，`mpc_no_tes -> mpc` 的 TES 增量为 {direction} {_fmt(abs(delta), 2)} CNY/月。"
        )
    if float(row.get("dr_event_count", 0.0) or 0.0) > 0:
        notes.append(
            f"DR 事件数为 {int(row.get('dr_event_count'))}，请求削减 {_fmt(row.get('dr_requested_reduction_kwh'), 2)} kWh，达成削减 {_fmt(row.get('dr_served_reduction_kwh'), 2)} kWh。"
        )
    if str(row.get("peak_cap_reference_source", "")).strip() not in {"", "nan"}:
        notes.append(
            f"Peak-cap 参考峰值为 {_fmt(row.get('peak_cap_reference_kw'), 2)} kW，最大 slack 为 {_fmt(row.get('peak_slack_max_kw'), 6)} kW。"
        )
    if not events.empty:
        revenue = float(events.get("dr_revenue_cny", pd.Series([0.0])).sum())
        notes.append(f"事件表记录 {len(events)} 条事件，情景估算 DR 收益为 {_fmt(revenue, 2)} CNY。")
    return notes


def _case_report_markdown(
    row: pd.Series,
    run_dir: Path,
    figures: list[str],
    notes: list[str],
    events: pd.DataFrame,
) -> str:
    scenario_id = str(row["scenario_id"])
    metrics = [
        ("Controller", row.get("controller_type")),
        ("Steps", row.get("closed_loop_steps")),
        ("Total cost CNY", _fmt(row.get("total_cost"), 2)),
        ("Grid import kWh", _fmt(row.get("grid_import_kwh"), 2)),
        ("Peak grid kW", _fmt(row.get("peak_grid_kw"), 2)),
        ("Temp violation degree-hours", _fmt(row.get("temp_violation_degree_hours"), 4)),
        ("Fallback count", int(row.get("fallback_count", 0) or 0)),
        ("Solve time p95 s", _fmt(row.get("solve_time_p95_s"), 4)),
        ("Final SOC", _fmt(row.get("final_soc_after_last_update"), 4)),
        ("TES charge kWh_th", _fmt(row.get("tes_charge_kwh_th"), 2)),
        ("TES discharge kWh_th", _fmt(row.get("tes_discharge_kwh_th"), 2)),
        ("DR event count", int(row.get("dr_event_count", 0) or 0)),
    ]
    lines = [
        f"# {scenario_id}",
        "",
        f"- Category: `{_category(scenario_id)}`",
        f"- Raw run directory: `{run_dir}`",
        "",
        "## Key Metrics",
        "",
        "| Metric | Value |",
        "|---|---:|",
    ]
    for key, value in metrics:
        lines.append(f"| {key} | {value} |")
    lines += ["", "## Analysis", ""]
    lines += [f"- {note}" for note in notes]
    if not events.empty:
        lines += ["", "## Event Table", "", events.to_markdown(index=False)]
    lines += ["", "## Figures", ""]
    captions = [
        "Grid/PV/power trace",
        "TES charge/discharge and SOC",
        "Temperature constraints",
        "Tariff, critical-peak/fallback flags, and solver time",
    ]
    for fig, caption in zip(figures, captions):
        lines += [f"### {caption}", "", f"![{caption}]({fig})", ""]
    return "\n".join(lines).rstrip() + "\n"


def _summary_report_markdown(root: Path, out: Path, summary: pd.DataFrame, index: pd.DataFrame) -> str:
    category = summary.assign(category=summary["scenario_id"].map(_category))
    by_category = (
        category.groupby("category")
        .agg(
            runs=("scenario_id", "count"),
            total_cost_mean=("total_cost", "mean"),
            peak_grid_mean=("peak_grid_kw", "mean"),
            temp_violation_max=("temp_violation_degree_hours", "max"),
            fallback_sum=("fallback_count", "sum"),
        )
        .reset_index()
    )
    by_controller = (
        summary.groupby("controller_type")
        .agg(
            runs=("scenario_id", "count"),
            total_cost_mean=("total_cost", "mean"),
            peak_grid_mean=("peak_grid_kw", "mean"),
            temp_violation_mean=("temp_violation_degree_hours", "mean"),
            fallback_sum=("fallback_count", "sum"),
        )
        .reset_index()
    )
    paired_path = root / "analysis" / "paired_comparisons.csv"
    paired = pd.read_csv(paired_path) if paired_path.exists() else pd.DataFrame()
    top_temp = summary.sort_values("temp_violation_degree_hours", ascending=False).head(10)[
        ["scenario_id", "controller_type", "temp_violation_degree_hours", "fallback_count", "total_cost"]
    ]
    lines = [
        "# China TOU/DR Matrix Full Result Report",
        "",
        f"- Result root: `{root}`",
        f"- Report root: `{out}`",
        f"- Case reports: {len(index)}",
        f"- Figures generated: {len(index) * 4}",
        "- Plot style: MATLAB-like color order, white axes, grid lines, compact time axis.",
        "",
        "## Overall",
        "",
        f"- Completed runs: {len(summary)}",
        f"- Fallback count total: {int(summary['fallback_count'].sum())}",
        f"- Minimum feasible rate: {_fmt(summary['feasible_rate'].min(), 6)}",
        f"- Minimum optimal rate: {_fmt(summary['optimal_rate'].min(), 6)}",
        f"- Maximum solve time p95: {_fmt(summary['solve_time_p95_s'].max(), 4)} s",
        f"- Maximum temperature violation: {_fmt(summary['temp_violation_degree_hours'].max(), 4)} degree-hours",
        "",
        "## Paired TES-MPC Result",
        "",
    ]
    if not paired.empty:
        lines += [paired.to_markdown(index=False), ""]
    lines += [
        "## Category Summary",
        "",
        by_category.to_markdown(index=False, floatfmt=".3f"),
        "",
        "## Controller Summary",
        "",
        by_controller.to_markdown(index=False, floatfmt=".3f"),
        "",
        "## Highest Temperature-Violation Cases",
        "",
        top_temp.to_markdown(index=False, floatfmt=".3f"),
        "",
        "## Case Report Index",
        "",
        "| Scenario | Category | Controller | Report |",
        "|---|---|---|---|",
    ]
    for _, row in index.iterrows():
        lines.append(
            f"| `{row['scenario_id']}` | {row['category']} | {row['controller_type']} | [{row['report']}]({row['report']}) |"
        )
    return "\n".join(lines).rstrip() + "\n"


def _category(scenario_id: str) -> str:
    if scenario_id.startswith("tou_screen"):
        return "TOU screening"
    if scenario_id.startswith("tou_full"):
        return "TOU full compare"
    if scenario_id.startswith("peakcap"):
        return "Peak-cap"
    if scenario_id.startswith("dr_"):
        return "DR event"
    if scenario_id.startswith("robust"):
        return "Robustness"
    return "Other"


def _fmt(value: Any, ndigits: int = 2) -> str:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return str(value)
    if math.isnan(numeric):
        return ""
    return f"{numeric:,.{ndigits}f}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--result-dir", default="results/china_tou_dr_matrices_20260506")
    parser.add_argument("--output-dir", default=None)
    args = parser.parse_args()
    print(generate_result_reports(args.result_dir, args.output_dir))


if __name__ == "__main__":
    main()
