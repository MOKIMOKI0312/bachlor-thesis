from datetime import datetime

import pytest

from mpc_v2.core.io_schemas import Action, Observation, SchemaValidationError, load_yaml


def test_observation_and_action_schema_validates_fixed_dt():
    obs = Observation(
        timestamp=datetime(2025, 1, 1),
        dt_h=0.25,
        air_temperature_C=24.0,
        outdoor_drybulb_C=30.0,
        ite_power_kw=18000.0,
        facility_power_kw=22000.0,
        tes_soc=0.5,
        tes_tank_temp_C=7.0,
        current_pv_kw=1000.0,
        current_price_usd_per_mwh=80.0,
        chiller_cop=5.0,
        pue_actual=1.2,
    )
    obs.validate()
    Action(tes_signed_target=100.0, tes_charge_kwth=100.0, tes_discharge_kwth=0.0).validate()


def test_observation_rejects_non_15min_dt():
    obs = Observation(
        timestamp=datetime(2025, 1, 1),
        dt_h=1.0,
        air_temperature_C=24.0,
        outdoor_drybulb_C=30.0,
        ite_power_kw=18000.0,
        facility_power_kw=22000.0,
        tes_soc=0.5,
        tes_tank_temp_C=7.0,
        current_pv_kw=1000.0,
        current_price_usd_per_mwh=80.0,
        chiller_cop=5.0,
        pue_actual=1.2,
    )
    with pytest.raises(SchemaValidationError):
        obs.validate()


def test_base_config_truth_table():
    cfg = load_yaml("mpc_v2/config/base.yaml")
    assert cfg["time"]["dt_h"] == 0.25
    assert cfg["time"]["horizon_steps"] == 192
    assert cfg["temperature"]["min_C"] == 18.0
    assert cfg["temperature"]["max_C"] == 27.0
    assert cfg["paths"]["pv_csv"].endswith("CHN_Nanjing_PV_6MWp_hourly.csv")
    assert cfg["paths"]["price_csv"].endswith("Jiangsu_TOU_2025_hourly.csv")

