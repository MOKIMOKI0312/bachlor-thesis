import importlib
import json

import pandas as pd


pkg = importlib.import_module("Nanjing-DataCenter-TES-EnergyPlus.controller.energyplus_mpc.common")
extract_mod = importlib.import_module("Nanjing-DataCenter-TES-EnergyPlus.controller.energyplus_mpc.extract_params")
identify_mod = importlib.import_module("Nanjing-DataCenter-TES-EnergyPlus.controller.energyplus_mpc.identify_params")
audit_mod = importlib.import_module("Nanjing-DataCenter-TES-EnergyPlus.controller.energyplus_mpc.audit_results")
runner_mod = importlib.import_module("Nanjing-DataCenter-TES-EnergyPlus.controller.energyplus_mpc.run_energyplus_mpc")


def test_tes_set_mapping_matches_energyplus_sign_convention():
    assert pkg.tes_set_from_q_tes_net(4500.0, 4500.0) == -1.0
    assert pkg.tes_set_from_q_tes_net(-4500.0, 4500.0) == 1.0
    assert pkg.tes_set_from_q_tes_net(0.0, 4500.0) == 0.0


def test_static_parameter_extraction_finds_existing_tes_interfaces():
    params = extract_mod.extract_static_params("Nanjing-DataCenter-TES-EnergyPlus/model/Nanjing_DataCenter_TES.epJSON")
    assert params["tes"]["object_name"] == "Chilled Water Tank"
    assert params["tes"]["max_flow_kg_s_from_ems"] == 389.0
    assert params["actuators"]["tes_set"]["key"] == "TES_Set"
    assert "tes_soc" in params["variables"]
    assert "tes_use_avail_echo" in params["variables"]


def test_timeseries_identification_returns_positive_proxy_values():
    identified = identify_mod.identify_from_timeseries(
        "Nanjing-DataCenter-TES-EnergyPlus/out/energyplus_nanjing/timeseries_15min.csv"
    )
    assert identified["rows"] > 100
    assert identified["facility_base_kw_median"] > 0.0
    assert identified["p_nonplant_kw_median"] > 0.0
    assert identified["chiller_fit"]["a_kw_per_kwth"] > 0.0


def test_energyplus_mpc_audit_flags_missing_cases(tmp_path):
    case = tmp_path / "no_control"
    case.mkdir()
    pd.DataFrame([{"steps": 1, "exit_code": 0}]).to_csv(case / "summary.csv", index=False)
    (case / "run_manifest.json").write_text(json.dumps({}), encoding="utf-8")
    issues = audit_mod.audit_root(tmp_path)
    assert any("missing case directory" in issue for issue in issues)


def test_auto_record_start_chooses_active_chiller_window():
    runner = runner_mod.EnergyPlusMpcRunner(
        controller="no_control",
        max_steps=96,
        eplus_root="C:/Users/18430/EnergyPlus-23.1.0/EnergyPlus-23.1.0-87ed9199d4-Windows-x86_64",
        model="Nanjing-DataCenter-TES-EnergyPlus/model/Nanjing_DataCenter_TES.epJSON",
        weather="Nanjing-DataCenter-TES-EnergyPlus/weather/CHN_JS_Nanjing.582380_TMYx.2009-2023.epw",
        params_path="Nanjing-DataCenter-TES-EnergyPlus/controller/energyplus_mpc/config/energyplus_mpc_params.yaml",
        baseline_timeseries="Nanjing-DataCenter-TES-EnergyPlus/out/energyplus_nanjing/timeseries_15min.csv",
        price_csv="Nanjing-DataCenter-TES-EnergyPlus/inputs/Jiangsu_TOU_2025_hourly.csv",
        pv_csv="Nanjing-DataCenter-TES-EnergyPlus/inputs/CHN_Nanjing_PV_6MWp_hourly.csv",
        raw_output_dir="Nanjing-DataCenter-TES-EnergyPlus/out/test_unused",
        selected_output_root="results/test_unused",
    )
    assert runner.record_start_step > 0
