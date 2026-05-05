from mpc_v2.core.io_schemas import load_yaml


def test_thesis_core_scenario_set_contains_required_names():
    cfg = load_yaml("mpc_v2/config/scenario_sets.yaml")
    required = {
        "baseline_no_tes",
        "tes_mpc_perfect",
        "tes_mpc_pv_g05",
        "tes_mpc_pv_g10",
        "tes_mpc_pv_g20",
        "hot_week",
        "mild_week",
        "tariff_low",
        "tariff_base",
        "tariff_high",
    }
    assert set(cfg["scenario_sets"]["thesis_core"]) == required
    assert required <= set(cfg["scenarios"])
