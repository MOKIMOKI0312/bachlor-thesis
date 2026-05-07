from mpc_v2.core.io_schemas import load_yaml
from mpc_v2.scripts.run_validation_matrix import run_validation_matrix


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


def test_china_tou_dr_scenario_sets_are_declared():
    cfg = load_yaml("mpc_v2/config/scenario_sets.yaml")
    assert {
        "china_tou_screening_smoke",
        "china_tou_full_compare",
        "china_dr_peakcap_core",
        "china_robustness_core",
    } <= set(cfg["scenario_sets"])
    required = set().union(
        cfg["scenario_sets"]["china_tou_screening_smoke"],
        cfg["scenario_sets"]["china_tou_full_compare"],
        cfg["scenario_sets"]["china_dr_peakcap_core"],
        cfg["scenario_sets"]["china_robustness_core"],
    )
    assert required <= set(cfg["scenarios"])
    assert any(cfg["scenarios"][name].get("tariff_template") == "beijing" for name in required)
    assert any(cfg["scenarios"][name].get("dr_enabled") is True for name in required)


def test_peak_cap_reference_can_be_derived_from_source_scenario(tmp_path):
    scenario_path = tmp_path / "derived_peak.yaml"
    scenario_path.write_text(
        """
scenario_sets:
  derived_peak_test:
    - capped_case
scenarios:
  ref_case:
    controller_type: mpc_no_tes
    closed_loop_steps: 1
    horizon_steps: 4
  capped_case:
    controller_type: mpc
    closed_loop_steps: 1
    horizon_steps: 4
    peak_cap_ratio: 0.95
    peak_cap_reference_source: ref_case
""",
        encoding="utf-8",
    )
    out = run_validation_matrix(
        config_path="mpc_v2/config/base.yaml",
        scenario_path=scenario_path,
        scenario_set="derived_peak_test",
        steps=1,
        output_dir=tmp_path / "runs",
    )
    rows = load_yaml(scenario_path)
    assert "ref_case" in rows["scenarios"]
    summary = __import__("pandas").read_csv(out / "validation_summary.csv")
    assert summary["peak_cap_reference_kw"].iloc[0] > 0.0
