from mpc_v2.kim_lite.config import load_config
from mpc_v2.kim_lite.model import build_inputs, solve_paper_like_mpc


def test_peak_epigraph_and_peak_cap_slack_are_valid():
    cfg = load_config("mpc_v2/config/kim_lite_base.yaml")
    inputs = build_inputs(cfg, steps=16)
    base = solve_paper_like_mpc(cfg, inputs, tes_enabled=False)
    capped = solve_paper_like_mpc(cfg, inputs, peak_cap_kw=base.d_peak_kw * 0.99)
    assert capped.d_peak_kw + 1e-6 >= capped.p_grid_pos_kw.max()
    assert (capped.peak_slack_kw >= -1e-8).all()
    assert ((capped.p_grid_pos_kw - capped.peak_slack_kw) <= base.d_peak_kw * 0.99 + 1e-5).all()
    assert capped.mode_integrality == "strict"
    assert capped.status != "optimal_relaxed_modes"
    assert capped.mode_fractionality_max <= 1e-6


def test_peak_cap_relaxed_modes_are_explicit():
    cfg = load_config("mpc_v2/config/kim_lite_base.yaml")
    inputs = build_inputs(cfg, steps=16)
    base = solve_paper_like_mpc(cfg, inputs, tes_enabled=False)
    relaxed = solve_paper_like_mpc(
        cfg,
        inputs,
        peak_cap_kw=base.d_peak_kw * 0.99,
        mode_integrality="relaxed",
    )
    assert relaxed.mode_integrality == "relaxed"
    assert relaxed.status == "optimal_relaxed_modes"
