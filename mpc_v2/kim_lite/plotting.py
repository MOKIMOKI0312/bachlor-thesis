"""Plotting helpers for Kim-lite result artifacts."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


def plot_representative_dispatch(monitor_csv: str | Path, output_png: str | Path, title: str) -> None:
    frame = pd.read_csv(monitor_csv)
    x = frame["step"]
    fig, axes = plt.subplots(4, 1, figsize=(11, 8), sharex=True)
    axes[0].plot(x, frame["price_cny_per_kwh"], color="#1f77b4")
    axes[0].set_ylabel("price")
    axes[1].plot(x, frame["soc"], label="SOC", color="#2ca02c")
    axes[1].set_ylabel("SOC")
    axes[2].plot(x, frame["Q_tes_net_kw_th"], color="#d62728")
    axes[2].axhline(0, color="black", linewidth=0.8)
    axes[2].set_ylabel("Q_tes_net")
    axes[3].plot(x, frame["P_grid_pos_kw"], label="grid", color="#9467bd")
    axes[3].plot(x, frame["P_pv_kw"], label="PV", color="#ff7f0e", alpha=0.8)
    axes[3].set_ylabel("kW")
    axes[3].set_xlabel("step")
    axes[3].legend(loc="best")
    fig.suptitle(title)
    fig.tight_layout()
    Path(output_png).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_png, dpi=160)
    plt.close(fig)


def plot_summary_bar(summary_csv: str | Path, output_png: str | Path, x_col: str, y_col: str, title: str) -> None:
    frame = pd.read_csv(summary_csv)
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.bar(frame[x_col].astype(str), frame[y_col])
    ax.set_ylabel(y_col)
    ax.set_title(title)
    ax.tick_params(axis="x", rotation=25)
    fig.tight_layout()
    Path(output_png).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_png, dpi=160)
    plt.close(fig)


def plot_xy(summary_csv: str | Path, output_png: str | Path, x_col: str, y_col: str, title: str) -> None:
    frame = pd.read_csv(summary_csv)
    fig, ax = plt.subplots(figsize=(8, 5))
    for controller, group in frame.groupby("controller"):
        ax.plot(group[x_col], group[y_col], marker="o", label=controller)
    ax.set_xlabel(x_col)
    ax.set_ylabel(y_col)
    ax.set_title(title)
    ax.legend(loc="best")
    fig.tight_layout()
    Path(output_png).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_png, dpi=160)
    plt.close(fig)
