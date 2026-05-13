"""Plot generation for Phase 3 sizing summaries."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def generate_phase3_plots(summary: pd.DataFrame, output_dir: str | Path) -> list[Path]:
    """Generate required Phase 3 PNG figures and return created paths."""

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    active = summary[summary["critical_peak_uplift"] > 0].copy()
    created: list[Path] = []
    warnings: list[str] = []
    specs = [
        ("critical_peak_suppression_ratio", "CP suppression ratio", "heatmap_cp_suppression_by_location.png"),
        ("peak_reduction_ratio", "Peak reduction ratio", "heatmap_peak_reduction_by_location.png"),
        ("pv_self_consumption_ratio", "PV self-consumption ratio", "heatmap_pv_self_consumption_by_location.png"),
    ]
    for metric, title, filename in specs:
        if metric not in active.columns or active[metric].notna().sum() == 0:
            warnings.append(f"Skipped {filename}: missing {metric}.")
            continue
        created.append(_heatmap_by_location(active, metric, title, out / filename))

    if {"tes_capacity_mwh_th", "critical_peak_suppression_ratio", "pv_capacity_mwp"}.issubset(active.columns):
        created.append(_tes_curves(active, out / "tes_capacity_cp_suppression_curves.png"))
    else:
        warnings.append("Skipped TES capacity curves: missing required columns.")

    if {"pv_self_consumption_ratio", "peak_reduction_ratio", "pv_capacity_mwp", "tes_capacity_mwh_th"}.issubset(
        active.columns
    ):
        created.append(_pareto_scatter(active, out / "pareto_capacity_recommendation_scatter.png"))
    else:
        warnings.append("Skipped Pareto scatter: missing required columns.")

    if warnings:
        (out / "plot_warnings.txt").write_text("\n".join(warnings) + "\n", encoding="utf-8")
    return created


def _heatmap_by_location(frame: pd.DataFrame, metric: str, title: str, path: Path) -> Path:
    locations = list(frame["location_id"].drop_duplicates())
    fig, axes = plt.subplots(1, len(locations), figsize=(5 * len(locations), 4), squeeze=False)
    vmin = float(frame[metric].min(skipna=True))
    vmax = float(frame[metric].max(skipna=True))
    if not np.isfinite(vmin) or not np.isfinite(vmax) or vmin == vmax:
        vmin, vmax = 0.0, max(1.0, vmax if np.isfinite(vmax) else 1.0)
    image = None
    for ax, location in zip(axes[0], locations):
        sub = frame[frame["location_id"] == location]
        pivot = sub.pivot_table(index="tes_capacity_mwh_th", columns="pv_capacity_mwp", values=metric, aggfunc="mean")
        pivot = pivot.sort_index().sort_index(axis=1)
        image = ax.imshow(pivot.to_numpy(float), origin="lower", aspect="auto", vmin=vmin, vmax=vmax, cmap="viridis")
        ax.set_title(str(location))
        ax.set_xlabel("PV capacity (MWp)")
        ax.set_ylabel("TES capacity (MWh_th)")
        ax.set_xticks(range(len(pivot.columns)))
        ax.set_xticklabels([_fmt(v) for v in pivot.columns])
        ax.set_yticks(range(len(pivot.index)))
        ax.set_yticklabels([_fmt(v) for v in pivot.index])
    fig.suptitle(title)
    if image is not None:
        fig.colorbar(image, ax=axes.ravel().tolist(), shrink=0.85, label=title)
    fig.savefig(path, dpi=160, bbox_inches="tight")
    plt.close(fig)
    return path


def _tes_curves(frame: pd.DataFrame, path: Path) -> Path:
    locations = list(frame["location_id"].drop_duplicates())
    fig, axes = plt.subplots(1, len(locations), figsize=(5 * len(locations), 4), squeeze=False)
    for ax, location in zip(axes[0], locations):
        sub = frame[frame["location_id"] == location]
        for pv, group in sub.groupby("pv_capacity_mwp"):
            ordered = group.sort_values("tes_capacity_mwh_th")
            ax.plot(
                ordered["tes_capacity_mwh_th"],
                ordered["critical_peak_suppression_ratio"],
                marker="o",
                label=f"{_fmt(pv)} MWp",
            )
        ax.set_title(str(location))
        ax.set_xlabel("TES capacity (MWh_th)")
        ax.set_ylabel("CP suppression ratio")
        ax.legend(title="PV capacity")
    fig.savefig(path, dpi=160, bbox_inches="tight")
    plt.close(fig)
    return path


def _pareto_scatter(frame: pd.DataFrame, path: Path) -> Path:
    locations = list(frame["location_id"].drop_duplicates())
    fig, axes = plt.subplots(1, len(locations), figsize=(5 * len(locations), 4), squeeze=False)
    for ax, location in zip(axes[0], locations):
        sub = frame[frame["location_id"] == location]
        sizes = 30.0 + 3.0 * sub["tes_capacity_mwh_th"].astype(float)
        sc = ax.scatter(
            sub["pv_self_consumption_ratio"],
            sub["critical_peak_suppression_ratio"],
            c=sub["pv_capacity_mwp"],
            s=sizes,
            cmap="plasma",
            alpha=0.8,
            edgecolors="black",
            linewidths=0.3,
        )
        frontier = sub[sub.get("is_pareto_frontier", False).astype(bool)]
        if not frontier.empty:
            ax.scatter(
                frontier["pv_self_consumption_ratio"],
                frontier["critical_peak_suppression_ratio"],
                facecolors="none",
                edgecolors="white",
                linewidths=1.5,
                s=30.0 + 3.0 * frontier["tes_capacity_mwh_th"].astype(float),
            )
        ax.set_title(str(location))
        ax.set_xlabel("PV self-consumption ratio")
        ax.set_ylabel("CP suppression ratio")
        fig.colorbar(sc, ax=ax, label="PV capacity (MWp)")
    fig.savefig(path, dpi=160, bbox_inches="tight")
    plt.close(fig)
    return path


def _fmt(value: object) -> str:
    value = float(value)
    if value.is_integer():
        return str(int(value))
    return "%g" % value
