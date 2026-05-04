"""Rolling economic MPC controller facade."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from mpc_v2.core.io_schemas import Action, ForecastBundle, load_yaml
from mpc_v2.core.mpc_problem_milp import EconomicMPCProblem, MPCSolution, MPCState, ObjectiveWeights, SolverConfig
from mpc_v2.core.pue_model import PUEParams
from mpc_v2.core.room_model import RoomParams
from mpc_v2.core.tes_model import TESParams


class EconomicTESMPCController:
    """Thin controller wrapper around the MILP problem."""

    def __init__(
        self,
        tes: TESParams,
        room: RoomParams,
        pue: PUEParams,
        weights: ObjectiveWeights,
        solver: SolverConfig,
        dt_h: float = 0.25,
    ):
        self.problem = EconomicMPCProblem(tes, room, pue, weights, solver, dt_h=dt_h)
        self.previous_solution: MPCSolution | None = None

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "EconomicTESMPCController":
        dt_h = float(config["time"]["dt_h"])
        return cls(
            tes=TESParams.from_config(config["tes"]),
            room=RoomParams.from_config(config["room"]),
            pue=PUEParams.from_config(config["pue"]),
            weights=ObjectiveWeights.from_config(config["objective"]),
            solver=SolverConfig.from_config(config["solver"]),
            dt_h=dt_h,
        )

    @classmethod
    def from_yaml(cls, path: str | Path) -> "EconomicTESMPCController":
        return cls.from_config(load_yaml(path))

    def solve(self, state: MPCState, forecast: ForecastBundle) -> MPCSolution:
        solution = self.problem.solve(state, forecast)
        self.previous_solution = solution
        return solution

    def compute_action(self, state: MPCState, forecast: ForecastBundle) -> tuple[Action, MPCSolution]:
        solution = self.solve(state, forecast)
        action = Action(**solution.first_action())
        action.validate()
        return action, solution

