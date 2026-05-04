"""Generate M2-F1 W3 thesis figures.

The script reads existing W1/W2 artifacts only. It does not run simulations.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


REPO_DIR_NAME = "AI-Data-Center-Analysis_migration_bundle_20260311"
ALGO_ORDER = ["baseline_neutral", "heuristic", "mpc_milp"]
ALGO_LABELS = {
    "baseline_neutral": "Baseline",
    "heuristic": "Heuristic",
    "mpc_milp": "MILP",
}
ALGO_COLORS = {
    "baseline_neutral": "#2ca02c",
    "heuristic": "#ff7f0e",
    "mpc_milp": "#d62728",
}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def workspace_root() -> Path:
    return repo_root().parent


def resolve_path(raw: str | Path) -> Path:
    path = Path(raw)
    candidates = []
    if path.is_absolute():
        candidates.append(path)
    else:
        candidates.extend([Path.cwd() / path, workspace_root() / path, repo_root() / path])
        parts = path.parts
        if parts and parts[0] == REPO_DIR_NAME:
            stripped = Path(*parts[1:])
            candidates.extend([repo_root() / stripped, workspace_root() / path])
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    return candidates[0].resolve() if candidates else path.resolve()


def first_col(df: pd.DataFrame, aliases: Iterable[str]) -> str:
    for col in aliases:
        if col in df.columns:
            return col
    raise RuntimeError(f"missing expected column from aliases={list(aliases)}")


def load_monitor(path: str | Path, columns: list[str] | None = None) -> pd.DataFrame:
    resolved = resolve_path(path)
    if not resolved.exists():
        raise FileNotFoundError(resolved)
    if columns is None:
        return pd.read_csv(resolved)
    header = pd.read_csv(resolved, nrows=0)
    usecols = [c for c in columns if c in header.columns]
    return pd.read_csv(resolved, usecols=usecols)


def facility_to_kw(df: pd.DataFrame, facility_col: str = "Electricity:Facility", steps_per_hour: int = 4) -> np.ndarray:
    raw = df[facility_col].astype(float).to_numpy()
    median = float(np.nanmedian(np.abs(raw)))
    if "mwh_step" in df.columns:
        mwh_step = df["mwh_step"].astype(float).to_numpy()
        return mwh_step * steps_per_hour * 1000.0
    if median > 1.0e5:
        step_seconds = 3600.0 / steps_per_hour
        return raw / step_seconds / 1000.0
    if median < 100.0:
        return raw * steps_per_hour * 1000.0
    return raw / 1000.0


def minmax(values: np.ndarray) -> np.ndarray:
    arr = np.asarray(values, dtype=float)
    lo = float(np.nanmin(arr))
    hi = float(np.nanmax(arr))
    if not np.isfinite(lo) or not np.isfinite(hi) or hi <= lo:
        return np.zeros_like(arr)
    return (arr - lo) / (hi - lo)


def savefig(fig: plt.Figure, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Wrote {out_path}")


def plot_w2_head_to_head(trainlike_csv: Path, ood_csv: Path, out_dir: Path) -> Path:
    train = pd.read_csv(trainlike_csv).assign(design="trainlike")
    ood = pd.read_csv(ood_csv).assign(design="official_ood")
    df = pd.concat([train, ood], ignore_index=True)

    metrics = [
        ("cost_usd_total", "Cost (million USD)", 1.0e-6),
        ("pue_avg", "PUE", 1.0),
        ("comfort_violation_pct", "Comfort violation (%)", 1.0),
    ]
    designs = ["trainlike", "official_ood"]
    x = np.arange(len(designs))
    width = 0.23

    fig, axes = plt.subplots(1, 3, figsize=(12.5, 4.0), constrained_layout=True)
    for ax, (metric, ylabel, scale) in zip(axes, metrics):
        for idx, algo in enumerate(ALGO_ORDER):
            values = []
            for design in designs:
                row = df[(df["design"] == design) & (df["algorithm"] == algo)]
                values.append(float(row.iloc[0][metric]) * scale)
            ax.bar(
                x + (idx - 1) * width,
                values,
                width=width,
                label=ALGO_LABELS[algo],
                color=ALGO_COLORS[algo],
                edgecolor="#333333",
                linewidth=0.5,
            )
        ax.set_xticks(x)
        ax.set_xticklabels(["Trainlike", "Official OOD"])
        ax.set_ylabel(ylabel)
        ax.grid(axis="y", alpha=0.25)
        ax.spines[["top", "right"]].set_visible(False)
    axes[0].legend(frameon=False, loc="upper left")
    fig.suptitle("W2 head-to-head: no-TES baseline vs TES policies")
    out_path = out_dir / "fig1_w2_head_to_head.png"
    savefig(fig, out_path)
    return out_path


def plot_w1_robustness_curve(robustness_csv: Path, out_dir: Path) -> Path:
    df = pd.read_csv(robustness_csv)
    metrics = [
        ("sign_rate", "Sign rate"),
        ("dsoc_prepeak", "Delta SOC pre-peak"),
        ("dsoc_peak", "Delta SOC peak"),
        ("pue", "PUE"),
    ]
    gaussian = df[df["noise_mode"].eq("gaussian")]
    perfect = df[df["noise_mode"].eq("perfect")].iloc[0]
    persistence = df[df["noise_mode"].eq("persistence_h")]
    sigmas = [0.0, 0.05, 0.10, 0.20]
    markers = {1: "o", 4: "s", 12: "^"}

    fig, axes = plt.subplots(2, 2, figsize=(10.5, 7.2), constrained_layout=True)
    for ax, (metric, ylabel) in zip(axes.ravel(), metrics):
        means = [float(perfect[metric])]
        stds = [0.0]
        for sigma in sigmas[1:]:
            sub = gaussian[np.isclose(gaussian["sigma"], sigma)]
            means.append(float(sub[metric].mean()))
            stds.append(float(sub[metric].std(ddof=1)))
        ax.errorbar(
            sigmas,
            means,
            yerr=stds,
            marker="o",
            color="#1f77b4",
            linewidth=1.8,
            capsize=4,
            label="Gaussian noise",
        )
        for idx, (_, row) in enumerate(persistence.sort_values("persist_h").iterrows()):
            h = int(row["persist_h"])
            x_pos = 0.225 + idx * 0.018
            ax.scatter(
                [x_pos],
                [float(row[metric])],
                marker=markers.get(h, "D"),
                s=55,
                color="#9467bd",
                edgecolor="#333333",
                linewidth=0.5,
                label=f"Persistence h={h}",
            )
        ax.set_xlabel("Forecast noise sigma")
        ax.set_ylabel(ylabel)
        ax.set_xticks(sigmas + [0.225, 0.243, 0.261])
        ax.set_xticklabels(["0", "0.05", "0.10", "0.20", "h1", "h4", "h12"], rotation=0)
        ax.grid(alpha=0.25)
        ax.spines[["top", "right"]].set_visible(False)
    handles, labels = axes.ravel()[0].get_legend_handles_labels()
    by_label = dict(zip(labels, handles))
    fig.legend(by_label.values(), by_label.keys(), frameon=False, loc="upper center", ncol=4)
    fig.suptitle("W1-3 MILP robustness under forecast degradation", y=1.04)
    out_path = out_dir / "fig2_w1_robustness_curve.png"
    savefig(fig, out_path)
    return out_path


def plot_milp_soc_week(monitor_path: Path, out_dir: Path) -> Path:
    cols = [
        "step",
        "TES_SOC",
        "price_current_norm",
        "lmp_usd_per_mwh",
        "current_pv_kw",
    ]
    df = load_monitor(monitor_path, cols)
    start = 26 * 168 * 4
    window = 168 * 4
    sub = df.iloc[start : start + window].copy()
    if len(sub) < window:
        raise RuntimeError(f"week 26 slice too short: got {len(sub)} rows")
    soc_col = first_col(sub, ["TES_SOC"])
    price_col = first_col(sub, ["price_current_norm", "lmp_usd_per_mwh"])
    pv_col = first_col(sub, ["current_pv_kw"])
    hours = np.arange(len(sub), dtype=float) / 4.0
    price = sub[price_col].astype(float).to_numpy()
    if price_col == "price_current_norm":
        price_plot = minmax(price)
    else:
        price_plot = minmax(price)
    pv_plot = sub[pv_col].astype(float).to_numpy() / 6000.0

    fig, ax1 = plt.subplots(figsize=(11.5, 4.0), constrained_layout=True)
    ax2 = ax1.twinx()
    ax1.plot(hours, sub[soc_col].astype(float).to_numpy(), color="#1f77b4", linewidth=1.6, label="TES SOC")
    ax2.plot(hours, price_plot, color="#ff7f0e", linewidth=1.2, alpha=0.9, label="Price normalized")
    ax2.plot(hours, pv_plot, color="#bcbd22", linewidth=1.2, alpha=0.9, label="PV / 6000")
    ax1.set_xlabel("Hour in representative week")
    ax1.set_ylabel("TES SOC", color="#1f77b4")
    ax2.set_ylabel("Normalized price / PV ratio")
    ax1.set_ylim(-0.02, 1.02)
    ax2.set_ylim(-0.05, 1.05)
    ax1.grid(alpha=0.25)
    ax1.spines["top"].set_visible(False)
    ax2.spines["top"].set_visible(False)
    lines = ax1.get_lines() + ax2.get_lines()
    ax1.legend(lines, [line.get_label() for line in lines], frameon=False, loc="upper right")
    fig.suptitle("W2 MILP TES SOC trajectory, week 26")
    out_path = out_dir / "fig3_milp_soc_trajectory_week26.png"
    savefig(fig, out_path)
    return out_path


def locate_w2b_baseline_monitor(explicit: str | None) -> Path:
    if explicit:
        path = resolve_path(explicit)
        if path.exists():
            return path
        raise FileNotFoundError(path)
    candidates = [
        repo_root() / "runs" / "run" / "run-170" / "episode-001" / "monitor.csv",
        repo_root()
        / "runs"
        / "eval_m2"
        / "w2b_baseline_neutral_year_20260504_054338_neutral"
        / "monitor.csv",
    ]
    patterns = [
        "runs/**/w2b_baseline_neutral_year_20260504_054338*/episode-001/monitor.csv",
        "runs/**/w2b_baseline_neutral_year_20260504_054338*/monitor.csv",
    ]
    for pattern in patterns:
        candidates.extend(repo_root().glob(pattern))
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    raise FileNotFoundError("cannot locate W2-B baseline monitor")


def daily_profile(df: pd.DataFrame, values: np.ndarray, steps_per_day: int = 96) -> pd.Series:
    pos = np.arange(len(values)) % steps_per_day
    return pd.Series(values).groupby(pos).mean()


def plot_pv_load_diurnal(w2_monitor: Path, w2b_baseline_monitor: Path, out_dir: Path) -> Path:
    needed = ["current_pv_kw", "Electricity:Facility", "mwh_step"]
    w2 = load_monitor(w2_monitor, needed)
    w2b = load_monitor(w2b_baseline_monitor, needed)
    pv = daily_profile(w2, w2["current_pv_kw"].astype(float).to_numpy())
    train_load = daily_profile(w2, facility_to_kw(w2))
    ood_load = daily_profile(w2b, facility_to_kw(w2b))
    hours = np.arange(96, dtype=float) / 4.0

    fig, ax = plt.subplots(figsize=(9.0, 4.8), constrained_layout=True)
    ax.plot(hours, pv.to_numpy(), color="#bcbd22", linewidth=2.0, label="PV average")
    ax.plot(hours, train_load.to_numpy(), color="#1f77b4", linewidth=2.0, label="Trainlike load")
    ax.plot(hours, ood_load.to_numpy(), color="#d62728", linewidth=2.0, label="Official OOD load")
    ax.set_xlabel("Hour of day")
    ax.set_ylabel("Power (kW)")
    ax.set_xlim(0, 23.75)
    ax.grid(alpha=0.25)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False, loc="upper left")
    fig.suptitle("PV generation is below data-center load across the day")
    out_path = out_dir / "fig4_pv_load_diurnal_profile.png"
    savefig(fig, out_path)
    return out_path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", required=True, help="e.g. analysis/m2f1_w2_figures_<TS>")
    ap.add_argument(
        "--w2-trainlike-csv",
        default=f"{REPO_DIR_NAME}/analysis/m2f1_w2_scenario_compare_20260503_232820.csv",
    )
    ap.add_argument(
        "--w2-ood-csv",
        default=f"{REPO_DIR_NAME}/analysis/m2f1_w2b_scenario_compare_20260504_054338.csv",
    )
    ap.add_argument(
        "--w1-robustness-csv",
        default=f"{REPO_DIR_NAME}/analysis/m2f1_w1_3_robustness_curve_20260503_194137.csv",
    )
    ap.add_argument(
        "--w2-milp-monitor",
        default=f"{REPO_DIR_NAME}/runs/m2_tes_mpc_oracle/w2_mpc_milp_year_20260503_232820/monitor.csv",
    )
    ap.add_argument("--w2b-baseline-monitor", default=None)
    args = ap.parse_args()

    out_dir = resolve_path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    trainlike_csv = resolve_path(args.w2_trainlike_csv)
    ood_csv = resolve_path(args.w2_ood_csv)
    robustness_csv = resolve_path(args.w1_robustness_csv)
    w2_monitor = resolve_path(args.w2_milp_monitor)
    w2b_baseline = locate_w2b_baseline_monitor(args.w2b_baseline_monitor)

    outputs = [
        plot_w2_head_to_head(trainlike_csv, ood_csv, out_dir),
        plot_w1_robustness_curve(robustness_csv, out_dir),
        plot_milp_soc_week(w2_monitor, out_dir),
        plot_pv_load_diurnal(w2_monitor, w2b_baseline, out_dir),
    ]
    print("Generated figures:")
    for path in outputs:
        print(f"- {path}")


if __name__ == "__main__":
    main()
