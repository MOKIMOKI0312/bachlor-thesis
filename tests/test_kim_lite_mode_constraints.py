import pytest

from mpc_v2.kim_lite.config import load_config
from mpc_v2.kim_lite.model import build_inputs, solve_paper_like_mpc


def test_mode_selection_respects_bounds_or_off():
    cfg = load_config("mpc_v2/config/kim_lite_base.yaml")
    inputs = build_inputs(cfg, steps=16)
    solution = solve_paper_like_mpc(cfg, inputs)
    for q, mode_idx in zip(solution.q_chiller_kw_th, solution.mode_index):
        if mode_idx < 0:
            assert q <= 1e-6
        else:
            mode = cfg.modes[int(mode_idx)]
            assert q >= mode.q_min_kw_th - 1e-6
            assert q <= mode.q_max_kw_th + 1e-6


def test_relaxed_mode_integrality_is_blocked_for_multi_mode_proxy():
    cfg = load_config("mpc_v2/config/kim_lite_base.yaml")
    inputs = build_inputs(cfg, steps=4)

    with pytest.raises(RuntimeError, match="single-mode proxy"):
        solve_paper_like_mpc(cfg, inputs, mode_integrality="relaxed")
