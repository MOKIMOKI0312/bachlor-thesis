from mpc_v2.kim_lite.config import load_config
from mpc_v2.kim_lite.controller import run_controller_case
from mpc_v2.kim_lite.model import build_inputs


def test_grid_balance_is_reported_without_violation(tmp_path):
    cfg = load_config("mpc_v2/config/kim_lite_base.yaml")
    inputs = build_inputs(cfg, steps=16)
    _, summary = run_controller_case(cfg, inputs, "paper_like_mpc", "balance", tmp_path)
    assert summary["grid_balance_violation_count"] == 0
    assert summary["final_soc" if "final_soc" in summary else "soc_final"] is not None
