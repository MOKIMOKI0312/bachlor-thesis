"""Technical capacity recommendation rules for Phase 3."""

from __future__ import annotations

import numpy as np
import pandas as pd


OBJECTIVE_COLUMNS = [
    "critical_peak_suppression_ratio",
    "peak_reduction_ratio",
    "pv_facility_load_coverage_ratio",
    "pv_self_consumption_ratio",
]


def add_recommendation_columns(summary: pd.DataFrame, recommendation_cfg: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Add Pareto, diminishing-return, and recommended-capacity markers."""

    frame = summary.copy()
    frame["is_pareto_frontier"] = False
    frame["pareto_rank"] = np.nan
    frame["is_recommended"] = False

    active_mask = frame["critical_peak_uplift"] > 0
    active = frame[active_mask].copy()
    ranked_groups = []
    for _, group in active.groupby("location_id"):
        ranked_groups.append(_rank_pareto(group))
    if ranked_groups:
        ranked = pd.concat(ranked_groups)
        frame.loc[ranked.index, "is_pareto_frontier"] = ranked["pareto_rank"] == 1
        frame.loc[ranked.index, "pareto_rank"] = ranked["pareto_rank"]

    recommendations = build_capacity_recommendations(frame, recommendation_cfg)
    for _, rec in recommendations.iterrows():
        mask = (
            (frame["location_id"] == rec["location_id"])
            & (frame["pv_capacity_mwp"] == rec["recommended_pv_mwp"])
            & (frame["tes_capacity_mwh_th"] == rec["recommended_tes_mwh_th"])
            & (frame["critical_peak_uplift"] > 0)
        )
        frame.loc[mask, "is_recommended"] = True
    return frame, recommendations


def build_capacity_recommendations(summary: pd.DataFrame, recommendation_cfg: dict) -> pd.DataFrame:
    """Select the smallest capacity meeting 90% maximum technical effects."""

    active = summary[summary["critical_peak_uplift"] > 0].copy()
    if active.empty:
        return pd.DataFrame(columns=_recommendation_columns())

    peak_threshold = float(recommendation_cfg.get("peak_reduction_threshold_fraction", 0.90))
    cp_threshold = float(recommendation_cfg.get("cp_suppression_threshold_fraction", 0.90))
    min_self = float(recommendation_cfg.get("min_pv_self_consumption_ratio", 0.80))
    max_soc_delta = float(recommendation_cfg.get("max_allowed_soc_abs_delta", 0.05))

    rows = []
    for location_id, group in active.groupby("location_id"):
        max_cp = _nanmax_or_nan(group["critical_peak_suppression_ratio"])
        max_peak = _nanmax_or_nan(group["peak_reduction_ratio"])
        max_coverage = _nanmax_or_nan(group["pv_facility_load_coverage_ratio"])
        candidates = group.copy()
        mask = pd.Series(True, index=candidates.index)
        if np.isfinite(max_cp):
            mask &= candidates["critical_peak_suppression_ratio"] >= cp_threshold * max_cp
        peak_is_material = np.isfinite(max_peak) and max_peak > 0.005
        peak_note = ""
        if peak_is_material:
            mask &= candidates["peak_reduction_ratio"] >= peak_threshold * max_peak
        else:
            peak_note = "; annual peak reduction is negligible under this EnergyPlus boundary"
        mask &= candidates["pv_self_consumption_ratio"] >= min_self
        if "soc_delta" in candidates.columns:
            mask &= candidates["soc_delta"].abs() <= max_soc_delta
        selected = candidates[mask].copy()
        notes = "meets 90% maximum technical-effect rule" + peak_note
        rule_name = "minimum_capacity_90pct_effect"
        if selected.empty:
            selected = _best_available_candidates(
                candidates,
                max_cp=max_cp,
                max_peak=max_peak,
                cp_threshold=cp_threshold,
                peak_threshold=peak_threshold,
                min_self=min_self,
                max_soc_delta=max_soc_delta,
            )
            notes = "best available: no case met all thresholds"
            rule_name = "minimum_capacity_best_available"
        if "threshold_gap_score" not in selected.columns:
            selected["threshold_gap_score"] = 0.0
        selected["capacity_size_score"] = _capacity_score(selected)
        selected = selected.sort_values(
            [
                "threshold_gap_score",
                "capacity_size_score",
                "pv_capacity_mwp",
                "tes_capacity_mwh_th",
                "critical_peak_uplift",
            ]
        )
        choice = selected.iloc[0]
        rows.append(
            {
                "location_id": location_id,
                "recommended_pv_mwp": float(choice["pv_capacity_mwp"]),
                "recommended_tes_mwh_th": float(choice["tes_capacity_mwh_th"]),
                "rule_name": rule_name,
                "cp_suppression_ratio": float(choice["critical_peak_suppression_ratio"]),
                "peak_reduction_ratio": float(choice["peak_reduction_ratio"]),
                "pv_self_consumption_ratio": float(choice["pv_self_consumption_ratio"]),
                "pv_facility_load_coverage_ratio": float(choice["pv_facility_load_coverage_ratio"]),
                "max_cp_suppression_ratio": max_cp,
                "max_peak_reduction_ratio": max_peak,
                "max_pv_facility_load_coverage_ratio": max_coverage,
                "threshold_gap_score": float(choice.get("threshold_gap_score", 0.0)),
                "notes": notes,
            }
        )
    return pd.DataFrame(rows, columns=_recommendation_columns())


def _rank_pareto(group: pd.DataFrame) -> pd.DataFrame:
    remaining = group.copy()
    ranks = pd.Series(np.nan, index=group.index, dtype=float)
    rank = 1
    while not remaining.empty:
        frontier = _pareto_frontier_mask(remaining)
        ranks.loc[remaining.index[frontier]] = rank
        remaining = remaining.loc[~frontier]
        rank += 1
    out = group.copy()
    out["pareto_rank"] = ranks
    return out


def _pareto_frontier_mask(group: pd.DataFrame) -> np.ndarray:
    values = group[OBJECTIVE_COLUMNS + ["pv_capacity_mwp", "tes_capacity_mwh_th"]].copy()
    objective = values[OBJECTIVE_COLUMNS].replace([np.inf, -np.inf], np.nan).fillna(-np.inf).to_numpy(float)
    capacity = values[["pv_capacity_mwp", "tes_capacity_mwh_th"]].to_numpy(float)
    n = len(values)
    frontier = np.ones(n, dtype=bool)
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            better_or_equal_objective = np.all(objective[j] >= objective[i])
            smaller_or_equal_capacity = np.all(capacity[j] <= capacity[i])
            strict = np.any(objective[j] > objective[i]) or np.any(capacity[j] < capacity[i])
            if better_or_equal_objective and smaller_or_equal_capacity and strict:
                frontier[i] = False
                break
    return frontier


def _capacity_score(frame: pd.DataFrame) -> pd.Series:
    pv_max = max(1e-9, float(frame["pv_capacity_mwp"].max()))
    tes_max = max(1e-9, float(frame["tes_capacity_mwh_th"].max()))
    return frame["pv_capacity_mwp"] / pv_max + frame["tes_capacity_mwh_th"] / tes_max


def _best_available_candidates(
    candidates: pd.DataFrame,
    max_cp: float,
    max_peak: float,
    cp_threshold: float,
    peak_threshold: float,
    min_self: float,
    max_soc_delta: float,
) -> pd.DataFrame:
    selected = candidates.copy()
    selected = selected[selected["pv_self_consumption_ratio"].notna()].copy()
    if selected.empty:
        selected = candidates.copy()
    cp_target = cp_threshold * max_cp if np.isfinite(max_cp) and max_cp > 0 else 0.0
    peak_target = peak_threshold * max_peak if np.isfinite(max_peak) and max_peak > 0 else None
    cp_gap = (cp_target - selected["critical_peak_suppression_ratio"].fillna(-np.inf)).clip(lower=0.0)
    if peak_target is None:
        peak_gap = pd.Series(0.0, index=selected.index)
    else:
        peak_gap = (peak_target - selected["peak_reduction_ratio"].fillna(-np.inf)).clip(lower=0.0)
    self_gap = (min_self - selected["pv_self_consumption_ratio"].fillna(-np.inf)).clip(lower=0.0)
    if "soc_delta" in selected.columns:
        soc_gap = (selected["soc_delta"].abs() - max_soc_delta).clip(lower=0.0)
    else:
        soc_gap = pd.Series(0.0, index=selected.index)
    selected["threshold_gap_score"] = cp_gap + peak_gap + self_gap + soc_gap
    return selected


def _nanmax_or_nan(series: pd.Series) -> float:
    values = pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan)
    return float(values.max()) if values.notna().any() else float("nan")


def _recommendation_columns() -> list[str]:
    return [
        "location_id",
        "recommended_pv_mwp",
        "recommended_tes_mwh_th",
        "rule_name",
        "cp_suppression_ratio",
        "peak_reduction_ratio",
        "pv_self_consumption_ratio",
        "pv_facility_load_coverage_ratio",
        "max_cp_suppression_ratio",
        "max_peak_reduction_ratio",
        "max_pv_facility_load_coverage_ratio",
        "threshold_gap_score",
        "notes",
    ]
