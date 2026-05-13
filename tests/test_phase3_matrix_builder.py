from mpc_v2.core.io_schemas import load_yaml
from mpc_v2.phase3_sizing.scenario_builder import build_scenario_matrix, scenario_manifest_frame


def test_phase3_matrix_builder_full_three_location_matrix():
    cfg = load_yaml("mpc_v2/config/phase3_pv_tes_sizing.yaml")
    locations = load_yaml("mpc_v2/config/phase3_locations.yaml")
    scenarios = build_scenario_matrix(cfg, locations, output_root="results/phase3_pv_tes_sizing/full_matrix")
    manifest = scenario_manifest_frame(scenarios)
    assert len(scenarios) == 150
    assert manifest["scenario_id"].is_unique
    required = {
        "scenario_id",
        "location_id",
        "pv_capacity_mwp",
        "tes_capacity_mwh_th",
        "critical_peak_uplift",
        "critical_peak_window_set",
        "controller",
        "run_dir",
        "status",
    }
    assert required <= set(manifest.columns)
