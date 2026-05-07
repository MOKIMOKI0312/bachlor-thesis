from datetime import datetime

import pytest

from mpc_v2.core.io_schemas import ForecastBundle, MPCAction, MPCState, SchemaValidationError, load_yaml


def test_base_config_keeps_public_input_paths():
    cfg = load_yaml("mpc_v2/config/base.yaml")
    assert cfg["time"]["dt_hours"] == 0.25
    assert cfg["paths"]["pv_csv"] == "Nanjing-DataCenter-TES-EnergyPlus/inputs/CHN_Nanjing_PV_6MWp_hourly.csv"
    assert cfg["paths"]["price_csv"] == "Nanjing-DataCenter-TES-EnergyPlus/inputs/Jiangsu_TOU_2025_hourly.csv"
    assert cfg["tes"]["initial_soc"] == pytest.approx(0.5)
    assert cfg["tes"]["soc_target"] == pytest.approx(0.5)


def test_state_action_and_forecast_schema_validate():
    MPCState(soc=0.5, room_temp_c=24.0).validate()
    MPCAction(
        q_ch_tes_kw_th=10.0,
        q_dis_tes_kw_th=0.0,
        q_chiller_kw_th=1010.0,
        q_load_kw_th=1000.0,
        plant_power_kw=200.0,
        u_ch=10.0 / 4500.0,
        u_dis=0.0,
    ).validate()
    bundle = ForecastBundle(
        timestamps=[datetime(2025, 1, 1)],
        outdoor_temp_forecast_c=[30.0],
        it_load_forecast_kw=[18000.0],
        pv_forecast_kw=[0.0],
        price_forecast=[0.029],
        base_facility_kw=[18000.0],
        base_cooling_kw_th=[2160.0],
    )
    bundle.validate(horizon_steps=1, dt_hours=0.25)


def test_action_rejects_simultaneous_charge_and_discharge():
    with pytest.raises(SchemaValidationError):
        MPCAction(
            q_ch_tes_kw_th=1.0,
            q_dis_tes_kw_th=1.0,
            q_chiller_kw_th=1.0,
            q_load_kw_th=0.0,
            plant_power_kw=1.0,
            u_ch=1.0 / 4500.0,
            u_dis=1.0 / 4500.0,
        ).validate()


def test_forecast_rejects_length_mismatch():
    bundle = ForecastBundle(
        timestamps=[datetime(2025, 1, 1)],
        outdoor_temp_forecast_c=[30.0],
        it_load_forecast_kw=[18000.0],
        pv_forecast_kw=[0.0],
        price_forecast=[0.029],
        base_facility_kw=[18000.0],
        base_cooling_kw_th=[2160.0],
    )
    with pytest.raises(SchemaValidationError, match="length mismatch"):
        bundle.validate(horizon_steps=2, dt_hours=0.25)
