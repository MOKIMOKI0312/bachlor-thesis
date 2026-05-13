import pandas as pd

from mpc_v2.phase3_sizing.metrics import add_marginal_metrics
from mpc_v2.phase3_sizing.recommendation import add_recommendation_columns


def test_recommendation_selects_smallest_capacity_meeting_90pct_rule():
    summary = pd.DataFrame(
        [
            _row("nanjing", 10, 9, 0.91, 0.91, 0.95, 0.30),
            _row("nanjing", 20, 18, 0.93, 0.93, 0.90, 0.40),
            _row("nanjing", 40, 36, 1.00, 1.00, 0.82, 0.50),
        ]
    )
    marked, recs = add_recommendation_columns(
        summary,
        {
            "peak_reduction_threshold_fraction": 0.90,
            "cp_suppression_threshold_fraction": 0.90,
            "min_pv_self_consumption_ratio": 0.80,
            "max_allowed_soc_abs_delta": 0.05,
        },
    )
    rec = recs.iloc[0]
    assert rec["recommended_pv_mwp"] == 10.0
    assert rec["recommended_tes_mwh_th"] == 9.0
    chosen = marked[marked["is_recommended"]].iloc[0]
    assert bool(chosen["is_pareto_frontier"])


def test_marginal_diminishing_return_marks_previous_capacity():
    summary = pd.DataFrame(
        [
            _row("nanjing", 20, 0, 0.00, 0.1, 0.9, 0.3),
            _row("nanjing", 20, 9, 0.50, 0.2, 0.9, 0.3),
            _row("nanjing", 20, 18, 0.52, 0.3, 0.9, 0.3),
            _row("nanjing", 20, 36, 0.521, 0.4, 0.9, 0.3),
        ]
    )
    out = add_marginal_metrics(summary)
    row_9 = out[out["tes_capacity_mwh_th"] == 9].iloc[0]
    assert bool(row_9["diminishing_return_after_this_capacity"])


def _row(location, pv, tes, cp, peak, self_ratio, coverage):
    return {
        "location_id": location,
        "pv_capacity_mwp": float(pv),
        "tes_capacity_mwh_th": float(tes),
        "critical_peak_uplift": 0.2,
        "critical_peak_suppression_ratio": float(cp),
        "peak_reduction_ratio": float(peak),
        "pv_self_consumption_ratio": float(self_ratio),
        "pv_facility_load_coverage_ratio": float(coverage),
        "soc_delta": 0.0,
    }
