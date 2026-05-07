from mpc_v2.kim_lite.config import load_config, load_yaml_mapping
from mpc_v2.scripts.run_kim_lite_closed_loop import run_kim_lite_closed_loop


def test_kim_lite_scenario_config_contains_required_phases():
    scenarios = load_yaml_mapping("mpc_v2/config/kim_lite_scenarios.yaml")
    for name in [
        "phase_a",
        "phase_b_attribution",
        "phase_c_tou",
        "phase_d_peakcap",
        "phase_e_signed_valve",
    ]:
        assert name in scenarios
    assert "storage_priority_neutral_tes" in scenarios["phase_b_attribution"]["controllers"]


def test_kim_lite_closed_loop_script_writes_monitor(tmp_path):
    cfg = load_config("mpc_v2/config/kim_lite_base.yaml")
    run_dir = run_kim_lite_closed_loop(
        config_path="mpc_v2/config/kim_lite_base.yaml",
        controller="paper_like_mpc",
        case_id="pytest_kim_lite",
        steps=8,
        output_root=str(tmp_path),
    )
    assert (run_dir / "monitor.csv").exists()
    assert cfg.default_steps == 96
