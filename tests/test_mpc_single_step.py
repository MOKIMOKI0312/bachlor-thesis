import math

from mpc_v2.core.controller import EconomicTESMPCController
from mpc_v2.core.forecast import ForecastBuilder
from mpc_v2.core.io_schemas import MPCState, load_yaml


def test_linear_mpc_single_solve_respects_bounds_and_terminal_soc():
    cfg = load_yaml("mpc_v2/config/base.yaml")
    forecast = ForecastBuilder.from_config(cfg).build(
        cfg["synthetic"]["start_timestamp"],
        horizon_steps=16,
        pv_error_sigma=0.0,
        seed=11,
        it_load_kw=cfg["synthetic"]["it_load_kw"],
        outdoor_base_c=cfg["synthetic"]["outdoor_base_c"],
        outdoor_amplitude_c=cfg["synthetic"]["outdoor_amplitude_c"],
    )
    controller = EconomicTESMPCController.from_config(cfg)
    solution = controller.solve(MPCState(soc=0.5, room_temp_c=24.0), forecast)
    action = solution.first_action(controller.tes)
    assert solution.status == "optimal"
    assert math.isfinite(solution.objective_value)
    assert 0.0 <= action.q_ch_tes_kw_th <= cfg["tes"]["q_ch_max_kw_th"]
    assert 0.0 <= action.q_dis_tes_kw_th <= cfg["tes"]["q_dis_max_kw_th"]
    assert action.q_ch_tes_kw_th * action.q_dis_tes_kw_th <= 1e-6
    assert abs(solution.soc[-1] - cfg["tes"]["soc_target"]) <= 1e-5
    assert (solution.grid_import_kw >= 0.0).all()
    assert (solution.pv_spill_kw >= 0.0).all()
