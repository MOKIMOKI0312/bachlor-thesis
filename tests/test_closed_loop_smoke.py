import json

import pandas as pd
import pytest

from mpc_v2.scripts.run_closed_loop import run_closed_loop


def test_no_tes_closed_loop_smoke_outputs_required_files(tmp_path):
    run_dir = run_closed_loop(
        config_path="mpc_v2/config/base.yaml",
        case_id="pytest_no_tes",
        steps=4,
        output_root=tmp_path,
        controller_mode="no_tes",
        horizon_steps_override=8,
    )
    _assert_required_run_outputs(run_dir, 4)


def test_mpc_closed_loop_smoke_outputs_required_files(tmp_path):
    run_dir = run_closed_loop(
        config_path="mpc_v2/config/base.yaml",
        case_id="pytest_mpc",
        steps=4,
        output_root=tmp_path,
        controller_mode="mpc",
        pv_error_sigma=0.05,
        seed=123,
        horizon_steps_override=8,
    )
    _assert_required_run_outputs(run_dir, 4)
    summary = json.loads((run_dir / "episode_summary.json").read_text(encoding="utf-8"))
    assert summary["feasible_rate"] >= 0.95


def test_rbc_closed_loop_smoke_outputs_required_files(tmp_path):
    run_dir = run_closed_loop(
        config_path="mpc_v2/config/base.yaml",
        case_id="pytest_rbc",
        steps=4,
        output_root=tmp_path,
        controller_mode="rbc",
        horizon_steps_override=8,
    )
    _assert_required_run_outputs(run_dir, 4)


def test_mpc_no_tes_closed_loop_keeps_tes_disabled(tmp_path):
    run_dir = run_closed_loop(
        config_path="mpc_v2/config/base.yaml",
        case_id="pytest_mpc_no_tes",
        steps=4,
        output_root=tmp_path,
        controller_mode="mpc_no_tes",
        horizon_steps_override=8,
    )
    _assert_required_run_outputs(run_dir, 4)
    monitor = pd.read_csv(run_dir / "monitor.csv")
    summary = json.loads((run_dir / "episode_summary.json").read_text(encoding="utf-8"))
    assert monitor["q_ch_tes_kw_th"].abs().max() <= 1e-8
    assert monitor["q_dis_tes_kw_th"].abs().max() <= 1e-8
    assert monitor["u_signed"].abs().max() <= 1e-8
    assert summary["final_soc_after_last_update"] == pytest.approx(summary["initial_soc"])
    assert summary["fallback_count"] == 0


def test_dr_closed_loop_writes_event_log(tmp_path):
    run_dir = run_closed_loop(
        config_path="mpc_v2/config/base.yaml",
        case_id="pytest_dr",
        steps=4,
        output_root=tmp_path,
        controller_mode="mpc",
        horizon_steps_override=8,
        dr_enabled=True,
        dr_event_type="realtime",
        dr_reduction_frac=0.10,
        dr_start_hour=0.0,
        dr_duration_hours=1.0,
        dr_baseline_kw=20000.0,
        dr_compensation_cny_per_kwh=4.8,
    )
    _assert_required_run_outputs(run_dir, 4)
    events = pd.read_csv(run_dir / "events.csv")
    summary = json.loads((run_dir / "episode_summary.json").read_text(encoding="utf-8"))
    assert len(events) == 1
    assert events["requested_reduction_kwh"].iloc[0] > 0.0
    assert summary["dr_event_count"] == 1


def _assert_required_run_outputs(run_dir, expected_steps):
    assert (run_dir / "config_effective.yaml").exists()
    assert (run_dir / "timeseries.csv").exists()
    assert (run_dir / "events.csv").exists()
    assert (run_dir / "summary.csv").exists()
    monitor = pd.read_csv(run_dir / "monitor.csv")
    solver = pd.read_csv(run_dir / "solver_log.csv")
    summary = json.loads((run_dir / "episode_summary.json").read_text(encoding="utf-8"))
    assert len(monitor) == expected_steps
    assert len(solver) == expected_steps
    assert summary["closed_loop_steps"] == expected_steps
    for name in [
        "q_chiller_kw_th",
        "q_load_kw_th",
        "plant_power_kw",
        "u_ch",
        "u_dis",
        "u_signed",
        "signed_du",
        "du_signed_max",
        "mode_index",
        "selected_mode_q_min_kw_th",
        "selected_mode_q_max_kw_th",
        "mode_specific_plr",
        "instant_chiller_cop",
        "cold_station_power_kw",
        "episode_peak_grid_so_far_kw",
        "predicted_peak_grid_kw",
        "cold_station_proxy_grid_import_kw",
        "cold_station_proxy_pv_spill_kw",
        "peak_slack_kw",
        "price_total_cny_mwh",
        "price_float_cny_mwh",
        "price_nonfloat_cny_mwh",
        "tou_stage",
        "cp_flag",
        "dr_flag",
        "dr_notice_type",
        "dr_req_kw",
        "dr_baseline_kw",
        "dr_event_id",
    ]:
        assert name in monitor.columns
    expected_grid = (monitor["it_load_kw"] + monitor["plant_power_kw"] - monitor["pv_actual_kw"]).clip(lower=0.0)
    expected_spill = (monitor["pv_actual_kw"] - monitor["it_load_kw"] - monitor["plant_power_kw"]).clip(lower=0.0)
    assert (monitor["grid_import_kw"] - expected_grid).abs().max() <= 1e-8
    assert (monitor["pv_spill_kw"] - expected_spill).abs().max() <= 1e-8
    assert ((monitor["q_load_kw_th"] + monitor["q_ch_tes_kw_th"]) <= monitor["q_chiller_kw_th"] + 1e-6).all()
    assert monitor["u_signed"].between(-1.0, 1.0).all()
    assert (monitor["signed_du"] <= monitor["du_signed_max"] + 1e-8).all()
    assert (monitor["u_signed"] - (monitor["u_ch"] - monitor["u_dis"])).abs().max() <= 1e-9
    expected_signed = monitor["q_ch_tes_kw_th"] / 4500.0 - monitor["q_dis_tes_kw_th"] / 4500.0
    assert (monitor["u_signed"] - expected_signed).abs().max() <= 1e-8
    for name in [
        "total_cost",
        "energy_cost",
        "demand_charge_cost",
        "cold_station_proxy_total_cost",
        "cold_station_proxy_energy_cost",
        "cold_station_proxy_grid_import_kwh",
        "cold_station_proxy_pv_spill_kwh",
        "grid_import_kwh",
        "peak_grid_kw",
        "peak_slack_max_kw",
        "pv_actual_kwh",
        "pv_used_kwh",
        "pv_spill_kwh",
        "facility_energy_kwh",
        "cold_station_energy_kwh",
        "it_energy_kwh",
        "pue_avg",
        "pue_p95",
        "avg_chiller_plr",
        "avg_mode_specific_plr",
        "weighted_avg_chiller_cop",
        "time_in_high_plr_region",
        "low_plr_hours",
        "high_plr_hours",
        "time_in_each_mode",
        "mode_switch_count",
        "initial_soc",
        "final_soc_after_last_update",
        "soc_delta",
        "soc_inventory_delta_kwh_th",
        "tes_charge_weighted_avg_price",
        "tes_discharge_weighted_avg_price",
        "tes_arbitrage_price_spread",
        "charge_steps",
        "discharge_steps",
        "idle_steps",
        "charge_discharge_switch_count",
        "max_signed_du",
        "signed_valve_violation_count",
        "physical_consistency_violation_count",
        "max_chiller_supply_deficit_kw_th",
        "dr_event_count",
        "dr_requested_reduction_kwh",
        "dr_served_reduction_kwh",
        "dr_response_rate_avg",
        "dr_revenue_cny",
        "optimal_rate",
        "feasible_rate",
        "fallback_count",
    ]:
        assert name in summary
    assert summary["peak_grid_kw"] == pytest.approx(monitor["grid_import_kw"].max())
    assert summary["physical_consistency_violation_count"] == 0
    assert summary["max_chiller_supply_deficit_kw_th"] <= 1e-6
    assert summary["charge_steps"] + summary["discharge_steps"] + summary["idle_steps"] == expected_steps
