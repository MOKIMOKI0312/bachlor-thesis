from mpc_v2.kim_lite.baseline import storage_priority, storage_priority_neutral
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
