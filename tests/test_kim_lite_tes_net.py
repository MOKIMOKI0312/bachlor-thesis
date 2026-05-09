import pytest

from mpc_v2.kim_lite.config import load_config
from mpc_v2.kim_lite.model import build_inputs, solve_paper_like_mpc


def test_q_tes_net_definition_and_soc_direction():
    cfg = load_config("mpc_v2/config/kim_lite_base.yaml")
    inputs = build_inputs(cfg, steps=24)
    solution = solve_paper_like_mpc(cfg, inputs)
    q_net = solution.q_chiller_kw_th - inputs.q_load_kw_th
    assert solution.q_tes_net_kw_th == pytest.approx(q_net)
    for k, q in enumerate(solution.q_tes_net_kw_th):
        if q > 1e-6:
            assert solution.soc[k + 1] >= solution.soc[k] - 1e-3
        if q < -1e-6:
            assert solution.soc[k + 1] <= solution.soc[k] + 1e-3


def test_signed_ramp_constrains_first_step_from_previous_action():
    cfg = load_config("mpc_v2/config/kim_lite_base.yaml")
    inputs = build_inputs(cfg, steps=8)

    solution = solve_paper_like_mpc(
        cfg,
        inputs,
        enforce_signed_ramp=True,
        previous_u_signed=1.0,
    )
    first_u = solution.q_tes_net_kw_th[0] / cfg.tes.q_abs_max_kw_th

    assert abs(first_u - 1.0) <= cfg.signed_du_max + 1e-6
