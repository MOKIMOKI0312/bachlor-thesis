import math

from mpc_v2.core.controller import EconomicTESMPCController
from mpc_v2.core.facility_model import FacilityModel, FacilityParams
from mpc_v2.core.forecast import ForecastBuilder
from mpc_v2.core.io_schemas import MPCState, load_yaml
from mpc_v2.core.room_model import RoomModel, RoomParams


def test_milp_single_solve_respects_first_action_bounds():
    cfg = load_yaml("mpc_v2/config/base.yaml")
    facility = FacilityModel(FacilityParams.from_config(cfg["facility"]))
    room = RoomModel(RoomParams.from_config(cfg["room"]), dt_hours=cfg["time"]["dt_hours"])
    forecast = ForecastBuilder(
        cfg["paths"]["pv_csv"],
        cfg["paths"]["price_csv"],
        facility,
        room,
        dt_hours=cfg["time"]["dt_hours"],
    ).build(
        cfg["synthetic"]["start_timestamp"],
        horizon_steps=8,
        pv_error_sigma=0.05,
        seed=11,
        it_load_kw=cfg["synthetic"]["it_load_kw"],
        outdoor_base_c=cfg["synthetic"]["outdoor_base_c"],
        outdoor_amplitude_c=cfg["synthetic"]["outdoor_amplitude_c"],
        outdoor_offset_c=0.0,
        tariff_multiplier=1.0,
    )
    controller = EconomicTESMPCController.from_config(cfg)
    solution = controller.solve(
        MPCState(soc=cfg["tes"]["initial_soc"], room_temp_c=cfg["room"]["initial_room_temp_c"]),
        forecast,
    )
    q_ch = solution.q_ch_tes_kw_th[0]
    q_dis = solution.q_dis_tes_kw_th[0]
    assert solution.status == "optimal"
    assert math.isfinite(solution.objective_value)
    assert 0.0 <= q_ch <= cfg["tes"]["q_ch_max_kw_th"] + 1e-7
    assert 0.0 <= q_dis <= cfg["tes"]["q_dis_max_kw_th"] + 1e-7
    assert q_ch * q_dis <= 1e-5
    assert solution.soc.min() >= cfg["tes"]["soc_physical_min"] - 1e-7
    assert solution.soc.max() <= cfg["tes"]["soc_physical_max"] + 1e-7
