import pandas as pd

from mpc_v2.phase3_sizing.metrics import add_relative_metrics, apply_critical_peak_uplift


def test_critical_peak_uplift_uses_explicit_window_only():
    index = pd.to_datetime(["2025-07-01 15:45", "2025-07-01 16:00", "2025-07-01 19:45", "2025-07-01 20:00"])
    base = pd.Series([100.0, 100.0, 100.0, 100.0], index=index)
    price, flag = apply_critical_peak_uplift(base, uplift=0.2, windows=[[16, 20]])
    assert list(flag) == [0, 1, 1, 0]
    assert list(price) == [100.0, 120.0, 120.0, 100.0]


def test_critical_peak_suppression_ratio_uses_grid_energy_reduction():
    rows = [
        {"location_id": "nanjing", "pv_capacity_mwp": 0, "tes_capacity_mwh_th": 0, "critical_peak_uplift": 0.0, "total_cost": 90.0, "peak_grid_kw": 1.0, "critical_peak_grid_kwh": 1.0},
        {"location_id": "nanjing", "pv_capacity_mwp": 0, "tes_capacity_mwh_th": 0, "critical_peak_uplift": 0.2, "total_cost": 95.0, "peak_grid_kw": 1.0, "critical_peak_grid_kwh": 1.0},
        {"location_id": "nanjing", "pv_capacity_mwp": 20, "tes_capacity_mwh_th": 0, "critical_peak_uplift": 0.0, "total_cost": 100.0, "peak_grid_kw": 1.0, "critical_peak_grid_kwh": 1.0},
        {"location_id": "nanjing", "pv_capacity_mwp": 20, "tes_capacity_mwh_th": 0, "critical_peak_uplift": 0.2, "total_cost": 120.0, "peak_grid_kw": 1.0, "critical_peak_grid_kwh": 1.0},
        {"location_id": "nanjing", "pv_capacity_mwp": 20, "tes_capacity_mwh_th": 18, "critical_peak_uplift": 0.0, "total_cost": 100.0, "peak_grid_kw": 1.0, "critical_peak_grid_kwh": 1.0},
        {"location_id": "nanjing", "pv_capacity_mwp": 20, "tes_capacity_mwh_th": 18, "critical_peak_uplift": 0.2, "total_cost": 130.0, "peak_grid_kw": 1.0, "critical_peak_grid_kwh": 0.5},
    ]
    out = add_relative_metrics(pd.DataFrame(rows))
    case = out[(out["pv_capacity_mwp"] == 20) & (out["tes_capacity_mwh_th"] == 18) & (out["critical_peak_uplift"] == 0.2)].iloc[0]
    assert case["critical_peak_cost_impact"] == 30.0
    assert case["critical_peak_suppression_ratio"] == 0.5
