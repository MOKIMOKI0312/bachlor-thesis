from mpc_v2.kim_lite.config import load_config
from mpc_v2.kim_lite.controller import run_controller_case
from mpc_v2.kim_lite.model import build_inputs


def test_grid_balance_is_reported_without_violation(tmp_path):
    cfg = load_config("mpc_v2/config/kim_lite_base.yaml")
    inputs = build_inputs(cfg, steps=16)
    _, summary = run_controller_case(cfg, inputs, "paper_like_mpc", "balance", tmp_path)
    assert summary["grid_balance_violation_count"] == 0
    assert summary["final_soc" if "final_soc" in summary else "soc_final"] is not None


def test_summary_reports_objective_split_and_cp_behavior(tmp_path):
    cfg = load_config("mpc_v2/config/kim_lite_base.yaml")
    inputs = build_inputs(cfg, steps=96, cp_uplift=0.2)
    _, summary = run_controller_case(
        cfg,
        inputs,
        "paper_like_mpc_tes",
        "mainline",
        tmp_path,
        enforce_signed_ramp=True,
    )
    for column in [
        "energy_cost",
        "peak_slack_penalty_cost",
        "objective_cost",
        "TES_discharge_during_cp_kwh_th",
        "TES_charge_during_valley_kwh_th",
        "grid_reduction_during_cp_kwh",
        "cp_hours",
    ]:
        assert column in summary
    assert summary["energy_cost"] == summary["cost_total"]
    assert summary["peak_slack_penalty_cost"] >= 0.0
    assert summary["cp_hours"] > 0.0
    assert summary["signed_valve_violation_count"] == 0
