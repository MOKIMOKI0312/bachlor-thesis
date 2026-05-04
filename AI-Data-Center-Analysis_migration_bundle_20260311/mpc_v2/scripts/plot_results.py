"""Generate standard MPC v2 smoke plots from monitor and solver logs."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


def plot_results(run_dir: str | Path) -> list[Path]:
    """Write the required diagnostic plots for one run directory."""

    run_dir = Path(run_dir)
    monitor = pd.read_csv(run_dir / "monitor.csv", parse_dates=["timestamp"])
    solver = pd.read_csv(run_dir / "solver_log.csv", parse_dates=["timestamp"])
    out = run_dir / "plots"
    out.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []

    paths.append(_plot_price_soc_tes(monitor, out / "price_soc_tes.png"))
    paths.append(_plot_power_stack(monitor, out / "power_flow.png"))
    paths.append(_plot_cost(monitor, out / "cost_bar.png"))
    paths.append(_plot_temperature(monitor, out / "temperature_constraints.png"))
    paths.append(_plot_pue(monitor, out / "pue_vs_outdoor.png"))
    paths.append(_plot_solver(solver, out / "solver_time_status.png"))
    return paths


def _plot_price_soc_tes(df: pd.DataFrame, path: Path) -> Path:
    fig, ax1 = plt.subplots(figsize=(10, 4))
    ax1.plot(df["timestamp"], df["price_usd_per_mwh"], label="price", color="black")
    ax1.set_ylabel("USD/MWh")
    ax2 = ax1.twinx()
    ax2.plot(df["timestamp"], df["tes_soc"], label="SOC", color="tab:green")
    ax2.plot(df["timestamp"], df["tes_charge_kwth"] / max(1.0, df["tes_charge_kwth"].max()), label="charge scaled", color="tab:blue", alpha=0.6)
    ax2.plot(df["timestamp"], df["tes_discharge_kwth"] / max(1.0, df["tes_discharge_kwth"].max()), label="discharge scaled", color="tab:red", alpha=0.6)
    ax2.set_ylabel("SOC / scaled TES")
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)
    return path


def _plot_power_stack(df: pd.DataFrame, path: Path) -> Path:
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(df["timestamp"], df["facility_power_kw"], label="facility")
    ax.plot(df["timestamp"], df["pv_kw"], label="PV")
    ax.plot(df["timestamp"], df["P_grid_kw"], label="grid")
    ax.plot(df["timestamp"], df["P_spill_kw"], label="spill")
    ax.legend()
    ax.set_ylabel("kW")
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)
    return path


def _plot_cost(df: pd.DataFrame, path: Path) -> Path:
    cost = df["price_usd_per_mwh"] * df["P_grid_kw"] * 0.25 / 1000.0
    fig, ax = plt.subplots(figsize=(5, 4))
    ax.bar(["total"], [cost.sum()])
    ax.set_ylabel("cost")
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)
    return path


def _plot_temperature(df: pd.DataFrame, path: Path) -> Path:
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(df["timestamp"], df["air_temperature_C"], label="room")
    ax.axhline(18.0, color="tab:blue", linestyle="--")
    ax.axhline(27.0, color="tab:red", linestyle="--")
    ax.set_ylabel("C")
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)
    return path


def _plot_pue(df: pd.DataFrame, path: Path) -> Path:
    fig, ax = plt.subplots(figsize=(5, 4))
    ax.scatter(df["outdoor_drybulb_C"], df["pue_actual"], s=10)
    ax.set_xlabel("outdoor C")
    ax.set_ylabel("PUE")
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)
    return path


def _plot_solver(df: pd.DataFrame, path: Path) -> Path:
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(df["timestamp"], df["solve_time_s"], marker=".")
    ax.set_ylabel("solve seconds")
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir")
    args = parser.parse_args()
    for path in plot_results(args.run_dir):
        print(path)


if __name__ == "__main__":
    main()

