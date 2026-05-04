import math

from mpc_v2.core.controller import EconomicTESMPCController
from mpc_v2.core.forecast import ForecastBuilder
from mpc_v2.core.io_schemas import load_yaml
from mpc_v2.core.mpc_problem_milp import MPCState
from mpc_v2.core.pue_model import PUEModel, PUEParams


def test_192_step_milp_single_solve_is_valid():
    cfg = load_yaml("mpc_v2/config/base.yaml")
    pue = PUEModel(PUEParams.from_config(cfg["pue"]))
    forecast = ForecastBuilder(cfg["paths"]["pv_csv"], cfg["paths"]["price_csv"], pue).build(
        cfg["synthetic"]["start_timestamp"],
        horizon_steps=192,
        pv_perturbation="g05",
        seed=11,
    )
    controller = EconomicTESMPCController.from_config(cfg)
    solution = controller.solve(
        MPCState(room_temperature_C=cfg["room"]["initial_temperature_C"], tes_soc=cfg["tes"]["initial_soc"]),
        forecast,
    )
    assert solution.status == "optimal"
    assert math.isfinite(solution.objective_value)
    assert len(solution.q_ch) == 192
    assert len(solution.soc) == 193
    assert solution.P_grid[0] >= -1e-7
    assert solution.P_spill[0] >= -1e-7

