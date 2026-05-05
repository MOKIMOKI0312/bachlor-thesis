"""Rolling controller facade around the MILP problem."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from mpc_v2.core.facility_model import FacilityParams
from mpc_v2.core.io_schemas import MPCAction, MPCState, load_yaml
from mpc_v2.core.mpc_problem_milp import EconomicMPCProblem, MPCSolution, ObjectiveWeights, SolverConfig
from mpc_v2.core.room_model import RoomParams
from mpc_v2.core.tes_model import TESParams


class EconomicTESMPCController:
    """Thin controller wrapper around the deterministic MILP."""

    def __init__(self, problem: EconomicMPCProblem):
        self.problem = problem
        self.previous_solution: MPCSolution | None = None

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "EconomicTESMPCController":
        problem = EconomicMPCProblem(
            tes=TESParams.from_config(config["tes"]),
            room=RoomParams.from_config(config["room"]),
            facility=FacilityParams.from_config(config["facility"]),
            weights=ObjectiveWeights.from_config(config["objective"]),
            solver=SolverConfig.from_config(config["solver"]),
            temp_min_c=float(config["temperature"]["min_c"]),
            temp_max_c=float(config["temperature"]["max_c"]),
            dt_hours=float(config["time"]["dt_hours"]),
        )
        return cls(problem)

    @classmethod
    def from_yaml(cls, path: str | Path) -> "EconomicTESMPCController":
        return cls.from_config(load_yaml(path))

    def solve(self, state: MPCState, forecast) -> MPCSolution:
        solution = self.problem.solve(state, forecast)
        self.previous_solution = solution
        return solution

    def compute_action(self, state: MPCState, forecast) -> tuple[MPCAction, MPCSolution]:
        solution = self.solve(state, forecast)
        q_ch, q_dis = solution.first_action()
        action = MPCAction(q_ch_tes_kw_th=q_ch, q_dis_tes_kw_th=q_dis)
        action.validate()
        return action, solution
