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


def test_thesis_chiller_tes_scenario_set_contains_baselines_and_stressors():
    cfg = load_yaml("mpc_v2/config/scenario_sets.yaml")
    required = {
        "chiller_no_tes_base",
        "chiller_rbc_base",
        "chiller_tes_mpc_base",
        "chiller_tes_pv_x2",
        "chiller_tes_pv_x3",
        "chiller_tes_tariff_high",
        "chiller_tes_demand_mid",
        "chiller_tes_demand_high",
        "chiller_tes_hot",
        "chiller_tes_mild",
    }
    assert set(cfg["scenario_sets"]["thesis_chiller_tes"]) == required
    assert required <= set(cfg["scenarios"])
