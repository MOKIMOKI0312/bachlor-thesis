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
