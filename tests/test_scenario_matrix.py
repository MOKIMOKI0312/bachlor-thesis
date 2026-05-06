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
        "chiller_tes_hot_day",
        "chiller_tes_mild_day",
        "chiller_tes_hot_week",
        "chiller_tes_mild_week",
    }
    assert required <= set(cfg["scenario_sets"]["thesis_chiller_tes"])
    assert required <= set(cfg["scenarios"])


def test_fixcheck_and_sensitivity_sets_are_declared():
    cfg = load_yaml("mpc_v2/config/scenario_sets.yaml")
    assert {"fixcheck_no_tes", "fixcheck_rbc", "fixcheck_mpc"} <= set(cfg["scenario_sets"]["fixcheck_smoke"])
    assert {"reviewfix_7day_no_tes", "reviewfix_7day_rbc", "reviewfix_7day_mpc"} <= set(
        cfg["scenario_sets"]["reviewfix_7day"]
    )
    assert {"pv3_no_tes", "pv3_rbc", "pv3_mpc", "pv5_no_tes", "pv5_rbc", "pv5_mpc"} <= set(
        cfg["scenario_sets"]["reviewfix_pv_contribution"]
    )
    assert {"peak3000_no_tes", "peak3000_rbc", "peak3000_mpc"} <= set(
        cfg["scenario_sets"]["reviewfix_peak_contribution"]
    )
    assert {
        "attribution_7day_no_tes_direct",
        "attribution_7day_mpc_no_tes",
        "attribution_7day_rbc_tes",
        "attribution_7day_mpc_tes",
        "attribution_7day_mpc_tes_soc_neutral",
    } <= set(cfg["scenario_sets"]["attribution_core"])
    assert {"terminal_soc", "pv_priority", "peak_cap"} <= set(cfg["sensitivity_sets"])
