import json

import pandas as pd
import pytest

from mpc_v2.core.io_schemas import UnsupportedFeatureError
from mpc_v2.scripts.run_closed_loop import run_closed_loop


def test_no_tes_rbc_and_mpc_closed_loop_write_required_files(tmp_path):
    for mode in ["no_tes", "rbc", "mpc"]:
        run_dir = run_closed_loop(
            config_path="mpc_v2/config/base.yaml",
            case_id=f"pytest_{mode}",
            steps=8,
            output_root=tmp_path,
            controller_mode=mode,
            horizon_steps_override=12,
            truncate_horizon_to_episode=True,
        )
        _assert_required_run_outputs(run_dir, expected_steps=8)


def test_mpc_24h_fixed_acceptance(tmp_path):
    run_dir = run_closed_loop(
        config_path="mpc_v2/config/base.yaml",
        case_id="pytest_mpc_24h",
        steps=96,
        output_root=tmp_path,
        controller_mode="mpc",
        horizon_steps_override=48,
        initial_soc=0.5,
        soc_target=0.5,
        truncate_horizon_to_episode=True,
    )
    _assert_required_run_outputs(run_dir, expected_steps=96)
    monitor = pd.read_csv(run_dir / "monitor.csv")
    summary = json.loads((run_dir / "episode_summary.json").read_text(encoding="utf-8"))
    assert summary["fallback_count"] == 0
    assert summary["soc_violation_count"] == 0
    assert summary["physical_consistency_violation_count"] == 0
    assert summary["final_soc_after_last_update"] == pytest.approx(0.5, abs=1e-5)
    assert ((monitor["q_ch_tes_kw_th"] > 1e-6) & (monitor["q_dis_tes_kw_th"] > 1e-6)).sum() == 0


def test_advanced_dr_options_fail_explicitly(tmp_path):
    with pytest.raises(UnsupportedFeatureError, match="advanced"):
        run_closed_loop(
            config_path="mpc_v2/config/base.yaml",
            case_id="pytest_dr_unsupported",
            steps=4,
            output_root=tmp_path,
            controller_mode="mpc",
            dr_enabled=True,
        )


def test_no_tes_keeps_soc_constant_for_compatibility(tmp_path):
    run_dir = run_closed_loop(
        config_path="mpc_v2/config/base.yaml",
        case_id="pytest_no_tes_soc",
        steps=8,
        output_root=tmp_path,
        controller_mode="no_tes",
    )
    summary = json.loads((run_dir / "episode_summary.json").read_text(encoding="utf-8"))
    assert summary["final_soc_after_last_update"] == pytest.approx(summary["initial_soc"])


def _assert_required_run_outputs(run_dir, expected_steps):
    for name in [
        "config_effective.yaml",
        "monitor.csv",
        "timeseries.csv",
        "solver_log.csv",
        "events.csv",
        "episode_summary.json",
        "summary.csv",
    ]:
        assert (run_dir / name).exists()
    monitor = pd.read_csv(run_dir / "monitor.csv")
    summary = json.loads((run_dir / "episode_summary.json").read_text(encoding="utf-8"))
    assert len(monitor) == expected_steps
    assert summary["closed_loop_steps"] == expected_steps
    for name in [
        "timestamp",
        "step",
        "controller_mode",
        "soc",
        "soc_after_update",
        "room_temp_c",
        "outdoor_temp_c",
        "it_load_kw",
        "pv_actual_kw",
        "price_cny_per_kwh",
        "q_ch_tes_kw_th",
        "q_dis_tes_kw_th",
        "q_chiller_kw_th",
        "q_load_kw_th",
        "plant_power_kw",
        "grid_import_kw",
        "pv_spill_kw",
        "step_cost",
        "fallback",
        "solver_status",
    ]:
        assert name in monitor.columns
    for name in [
        "total_cost",
        "peak_grid_kw",
        "fallback_count",
        "soc_min",
        "soc_max",
        "final_soc_after_last_update",
        "soc_violation_count",
    ]:
        assert name in summary
    expected_grid = (monitor["it_load_kw"] + monitor["plant_power_kw"] - monitor["pv_actual_kw"]).clip(lower=0.0)
    expected_spill = (monitor["pv_actual_kw"] - monitor["it_load_kw"] - monitor["plant_power_kw"]).clip(lower=0.0)
    assert (monitor["grid_import_kw"] - expected_grid).abs().max() <= 1e-8
    assert (monitor["pv_spill_kw"] - expected_spill).abs().max() <= 1e-8
