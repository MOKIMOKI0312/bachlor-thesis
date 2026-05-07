from mpc_v2.kim_lite.baseline import storage_priority
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
