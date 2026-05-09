import pytest

from mpc_v2.kim_lite.baseline import direct_no_tes, storage_priority, storage_priority_neutral
from mpc_v2.kim_lite.config import load_config
from mpc_v2.kim_lite.metrics import build_monitor, summarize_monitor
from mpc_v2.kim_lite.model import build_inputs


def test_storage_priority_charges_cheaper_than_it_discharges():
    cfg = load_config("mpc_v2/config/kim_lite_base.yaml")
    inputs = build_inputs(cfg, steps=96)
    solution = storage_priority(cfg, inputs)
    monitor = build_monitor("storage_priority", inputs, solution, cfg)
    summary = summarize_monitor(monitor, cfg, "storage_priority", "storage_priority")
    assert summary["TES_charge_kwh_th"] > 0.0
    assert summary["TES_discharge_kwh_th"] > 0.0
    assert summary["TES_charge_weighted_avg_price"] <= summary["TES_discharge_weighted_avg_price"]


def test_storage_priority_neutral_hits_terminal_soc_and_bounds():
    cfg = load_config("mpc_v2/config/kim_lite_base.yaml")
    inputs = build_inputs(cfg, steps=96)
    solution = storage_priority_neutral(cfg, inputs)
    monitor = build_monitor("storage_priority_neutral_tes", inputs, solution, cfg)
    summary = summarize_monitor(monitor, cfg, "storage_priority_neutral_tes", "storage_priority_neutral_tes")
    assert abs(summary["soc_final"] - cfg.tes.soc_target) <= 1e-3
    assert summary["soc_violation_count"] == 0
    assert summary["soc_min"] >= cfg.tes.soc_min - 1e-8
    assert summary["soc_max"] <= cfg.tes.soc_max + 1e-8


def test_fixed_dispatch_baselines_report_soc_from_final_q_tes_net():
    cfg = load_config("mpc_v2/config/kim_lite_base.yaml")
    inputs = build_inputs(cfg, steps=24)
    decay = 1.0 - cfg.tes.loss_per_h * cfg.dt_hours
    for solution in [storage_priority(cfg, inputs), storage_priority_neutral(cfg, inputs)]:
        for k, q_net in enumerate(solution.q_tes_net_kw_th):
            expected = decay * solution.soc[k] + q_net * cfg.dt_hours / cfg.tes.capacity_kwh_th
            assert solution.soc[k + 1] == pytest.approx(expected, abs=1e-8)


def test_direct_no_tes_has_zero_tes_net_and_constant_soc():
    cfg = load_config("mpc_v2/config/kim_lite_base.yaml")
    inputs = build_inputs(cfg, steps=24)
    solution = direct_no_tes(cfg, inputs)

    assert solution.q_tes_net_kw_th == pytest.approx([0.0] * len(inputs.timestamps), abs=1e-9)
    assert solution.soc == pytest.approx([cfg.tes.initial_soc] * (len(inputs.timestamps) + 1), abs=1e-9)
    assert solution.plant_tracking_error_kw_th is not None
