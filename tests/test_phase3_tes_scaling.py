import pytest

from mpc_v2.phase3_sizing.tes_scaling import build_tes_config


BASE_TES = {
    "capacity_kwh_th": 18000.0,
    "eta_ch": 0.94,
    "eta_dis": 0.92,
    "lambda_loss_per_h": 0.002,
    "q_ch_max_kw_th": 4500.0,
    "q_dis_max_kw_th": 4500.0,
    "initial_soc": 0.50,
    "soc_physical_min": 0.05,
    "soc_physical_max": 0.95,
    "soc_planning_min": 0.15,
    "soc_planning_max": 0.85,
    "soc_target": 0.50,
}


def test_tes_zero_disables_tes():
    cfg = build_tes_config(BASE_TES, 0)
    assert cfg["enabled"] is False
    assert cfg["q_tes_abs_max_kw_th"] == 0.0
    assert cfg["q_ch_max_kw_th"] == 0.0
    assert cfg["q_dis_max_kw_th"] == 0.0
    assert cfg["soc_constant"] is True


def test_tes_18_sets_capacity():
    cfg = build_tes_config(BASE_TES, 18)
    assert cfg["enabled"] is True
    assert cfg["capacity_mwh_th"] == 18.0
    assert cfg["capacity_kwh_th"] == 18000.0


def test_tes_72_keep_power_fixed_keeps_q_abs_max():
    cfg = build_tes_config(BASE_TES, 72)
    assert cfg["capacity_kwh_th"] == 72000.0
    assert cfg["q_tes_abs_max_kw_th"] == 4500.0


def test_negative_tes_capacity_raises():
    with pytest.raises(ValueError, match="non-negative"):
        build_tes_config(BASE_TES, -1)
