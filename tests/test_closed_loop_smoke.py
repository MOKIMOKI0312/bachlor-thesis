import json

import pandas as pd

from mpc_v2.scripts.run_closed_loop import run_closed_loop


def test_no_tes_closed_loop_smoke_outputs_required_files(tmp_path):
    run_dir = run_closed_loop(
        config_path="mpc_v2/config/base.yaml",
        case_id="pytest_no_tes",
        steps=4,
        output_root=tmp_path,
        controller_mode="no_tes",
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
    )
    _assert_required_run_outputs(run_dir, 4)


def _assert_required_run_outputs(run_dir, expected_steps):
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
        "mode_index",
        "cold_station_power_kw",
    ]:
        assert name in monitor.columns
    for name in [
        "total_cost",
        "energy_cost",
        "demand_charge_cost",
        "grid_import_kwh",
        "peak_grid_kw",
        "pv_actual_kwh",
        "pv_used_kwh",
        "pv_spill_kwh",
        "facility_energy_kwh",
        "cold_station_energy_kwh",
        "it_energy_kwh",
        "pue_avg",
        "pue_p95",
        "avg_chiller_plr",
        "time_in_high_plr_region",
        "optimal_rate",
        "feasible_rate",
        "fallback_count",
    ]:
        assert name in summary
