from mpc_v2.core.facility_model import (
    ChillerPlantModel,
    ChillerPlantParams,
    FacilityModel,
    FacilityParams,
    grid_and_spill_from_load_kw,
)
from mpc_v2.core.io_schemas import load_yaml
from mpc_v2.core.room_model import RoomModel, RoomParams
import pytest


def test_room_discharge_cools_relative_to_idle():
    cfg = load_yaml("mpc_v2/config/base.yaml")
    room = RoomModel(RoomParams.from_config(cfg["room"]), dt_hours=cfg["time"]["dt_hours"])
    base_cooling = room.base_cooling_kw_th(18000.0)
    idle = room.next_temperature(24.0, 30.0, 18000.0, base_cooling_kw_th=base_cooling, q_dis_tes_kw_th=0.0)
    discharging = room.next_temperature(
        24.0,
        30.0,
        18000.0,
        q_cooling_total_kw_th=base_cooling + 1000.0,
    )
    assert discharging < idle


def test_room_rejects_total_and_component_cooling_mix():
    cfg = load_yaml("mpc_v2/config/base.yaml")
    room = RoomModel(RoomParams.from_config(cfg["room"]), dt_hours=cfg["time"]["dt_hours"])
    with pytest.raises(ValueError, match="either q_cooling_total"):
        room.next_temperature(
            room_temp_c=24.0,
            outdoor_temp_c=30.0,
            it_load_kw=18000.0,
            q_cooling_total_kw_th=10000.0,
            q_dis_tes_kw_th=3000.0,
        )


def test_grid_pv_balance_splits_positive_and_negative_net_load():
    cfg = load_yaml("mpc_v2/config/base.yaml")
    model = FacilityModel(FacilityParams.from_config(cfg["facility"]))
    grid, spill, facility = model.grid_and_spill_kw(
        base_facility_kw=1000.0,
        q_ch_tes_kw_th=520.0,
        q_dis_tes_kw_th=0.0,
        pv_kw=900.0,
    )
    assert facility == 1100.0
    assert grid == 200.0
    assert spill == 0.0
    grid, spill, facility = model.grid_and_spill_kw(
        base_facility_kw=1000.0,
        q_ch_tes_kw_th=0.0,
        q_dis_tes_kw_th=0.0,
        pv_kw=1200.0,
    )
    assert facility == 1000.0
    assert grid == 0.0
    assert spill == 200.0


def test_whole_facility_grid_pv_balance_includes_it_load():
    grid, spill = grid_and_spill_from_load_kw(load_kw=18000.0 + 2500.0, pv_kw=6000.0)
    assert grid == 14500.0
    assert spill == 0.0
    grid, spill = grid_and_spill_from_load_kw(load_kw=18000.0 + 2500.0, pv_kw=22000.0)
    assert grid == 0.0
    assert spill == 1500.0


def test_chiller_plant_dispatch_uses_mode_affine_power():
    cfg = load_yaml("mpc_v2/config/base.yaml")
    model = ChillerPlantModel(ChillerPlantParams.from_config(cfg["chiller"]))
    q_effective, mode_index, plant_power = model.dispatch(5000.0, wet_bulb_c=25.0)
    assert q_effective >= 5000.0
    assert mode_index >= 0
    assert plant_power > 0.0
