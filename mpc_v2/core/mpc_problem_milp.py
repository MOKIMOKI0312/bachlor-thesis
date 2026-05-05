"""MILP construction and HiGHS solve path for TES-PV-TOU MPC."""

from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any

import numpy as np

from mpc_v2.core.facility_model import FacilityParams
from mpc_v2.core.io_schemas import ForecastBundle, MPCState, SolverUnavailableError
from mpc_v2.core.room_model import RoomParams
from mpc_v2.core.tes_model import TESParams


@dataclass(frozen=True)
class ObjectiveWeights:
    """Linear objective weights."""

    w_spill: float
    w_cycle: float
    w_temp: float
    w_soc: float
    w_switch: float
    w_terminal: float

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "ObjectiveWeights":
        return cls(**{field: float(config[field]) for field in cls.__dataclass_fields__})


@dataclass(frozen=True)
class SolverConfig:
    """MILP solver options."""

    name: str = "highs"
    time_limit_s: float = 30.0
    mip_rel_gap: float = 0.005

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "SolverConfig":
        return cls(
            name=str(config.get("name", "highs")),
            time_limit_s=float(config.get("time_limit_s", 30.0)),
            mip_rel_gap=float(config.get("mip_rel_gap", 0.005)),
        )


@dataclass(frozen=True)
class MPCSolution:
    """Parsed MILP solution arrays and solve metadata."""

    status: str
    success: bool
    objective_value: float
    solve_time_s: float
    mip_gap: float | None
    q_ch_tes_kw_th: np.ndarray
    q_dis_tes_kw_th: np.ndarray
    soc: np.ndarray
    room_temp_c: np.ndarray
    grid_import_kw: np.ndarray
    pv_spill_kw: np.ndarray
    s_temp_low: np.ndarray
    s_temp_high: np.ndarray
    s_soc_low: np.ndarray
    s_soc_high: np.ndarray
    du_ch: np.ndarray
    du_dis: np.ndarray
    s_terminal_low: float
    s_terminal_high: float

    def first_action(self) -> tuple[float, float]:
        q_ch = float(max(0.0, self.q_ch_tes_kw_th[0]))
        q_dis = float(max(0.0, self.q_dis_tes_kw_th[0]))
        if q_ch < 1e-6:
            q_ch = 0.0
        if q_dis < 1e-6:
            q_dis = 0.0
        return q_ch, q_dis


class EconomicMPCProblem:
    """Build and solve the deterministic linear MILP."""

    def __init__(
        self,
        tes: TESParams,
        room: RoomParams,
        facility: FacilityParams,
        weights: ObjectiveWeights,
        solver: SolverConfig,
        temp_min_c: float,
        temp_max_c: float,
        dt_hours: float,
    ):
        if solver.name.lower() != "highs":
            raise SolverUnavailableError(f"only HiGHS is supported, requested {solver.name}")
        tes.validate()
        room.validate()
        facility.validate()
        if temp_min_c >= temp_max_c:
            raise ValueError("temp_min_c must be below temp_max_c")
        self.tes = tes
        self.room = room
        self.facility = facility
        self.weights = weights
        self.solver = solver
        self.temp_min_c = float(temp_min_c)
        self.temp_max_c = float(temp_max_c)
        self.dt_hours = float(dt_hours)

    def solve(self, state: MPCState, forecast: ForecastBundle) -> MPCSolution:
        """Solve the current receding-horizon MILP."""

        try:
            from scipy.optimize import Bounds, LinearConstraint, milp
            from scipy.sparse import lil_matrix
        except Exception as exc:  # pragma: no cover
            raise SolverUnavailableError("scipy.optimize.milp/HiGHS is required") from exc

        state.validate()
        n = len(forecast.price_forecast)
        forecast.validate(horizon_steps=n, dt_hours=self.dt_hours)
        idx = _Index(n)
        c = np.zeros(idx.total)
        lb = np.zeros(idx.total)
        ub = np.full(idx.total, np.inf)
        integrality = np.zeros(idx.total)

        ub[idx.q_ch] = self.tes.q_ch_max_kw_th
        ub[idx.q_dis] = self.tes.q_dis_max_kw_th
        lb[idx.soc] = self.tes.soc_physical_min
        ub[idx.soc] = self.tes.soc_physical_max
        lb[idx.temp] = -100.0
        ub[idx.temp] = 100.0
        ub[idx.z_ch] = 1.0
        ub[idx.z_dis] = 1.0
        integrality[idx.z_ch] = 1
        integrality[idx.z_dis] = 1

        price = np.asarray(forecast.price_forecast, dtype=float)
        c[idx.grid] = price * self.dt_hours / 1000.0
        c[idx.spill] = self.weights.w_spill * self.dt_hours
        c[idx.q_ch] = self.weights.w_cycle * self.dt_hours
        c[idx.q_dis] = self.weights.w_cycle * self.dt_hours
        c[idx.s_t_low] = self.weights.w_temp * self.dt_hours
        c[idx.s_t_high] = self.weights.w_temp * self.dt_hours
        c[idx.s_soc_low] = self.weights.w_soc
        c[idx.s_soc_high] = self.weights.w_soc
        c[idx.du_ch] = self.weights.w_switch
        c[idx.du_dis] = self.weights.w_switch
        c[idx.s_terminal_low] = self.weights.w_terminal
        c[idx.s_terminal_high] = self.weights.w_terminal

        rows: list[tuple[dict[int, float], float, float]] = []
        rows.append(({idx.soc[0]: 1.0}, state.soc, state.soc))
        rows.append(({idx.temp[0]: 1.0}, state.room_temp_c, state.room_temp_c))

        dt = self.dt_hours
        loss_factor = 1.0 - self.tes.lambda_loss_per_h * dt
        ch_gain = self.tes.eta_ch * dt / self.tes.capacity_kwh_th
        dis_gain = dt / (self.tes.eta_dis * self.tes.capacity_kwh_th)
        temp_a = 1.0 - dt * self.room.outdoor_gain_fraction / self.room.thermal_time_constant_h
        temp_out_gain = dt * self.room.outdoor_gain_fraction / self.room.thermal_time_constant_h
        heat_gain = self.room.it_heat_gain_c_per_mwh * dt / 1000.0
        cooling_gain = self.room.cooling_gain_c_per_mwh * dt / 1000.0

        for t in range(n):
            rows.append(
                (
                    {
                        idx.soc[t + 1]: 1.0,
                        idx.soc[t]: -loss_factor,
                        idx.q_ch[t]: -ch_gain,
                        idx.q_dis[t]: dis_gain,
                    },
                    0.0,
                    0.0,
                )
            )

            temp_rhs = (
                temp_out_gain * float(forecast.outdoor_temp_forecast_c[t])
                + heat_gain * float(forecast.it_load_forecast_kw[t])
                - cooling_gain * float(forecast.base_cooling_kw_th[t])
            )
            rows.append(
                (
                    {
                        idx.temp[t + 1]: 1.0,
                        idx.temp[t]: -temp_a,
                        idx.q_dis[t]: cooling_gain,
                    },
                    temp_rhs,
                    temp_rhs,
                )
            )

            rows.append(({idx.q_ch[t]: 1.0, idx.z_ch[t]: -self.tes.q_ch_max_kw_th}, -np.inf, 0.0))
            rows.append(({idx.q_dis[t]: 1.0, idx.z_dis[t]: -self.tes.q_dis_max_kw_th}, -np.inf, 0.0))
            rows.append(({idx.z_ch[t]: 1.0, idx.z_dis[t]: 1.0}, -np.inf, 1.0))

            rows.append(({idx.temp[t + 1]: 1.0, idx.s_t_low[t]: 1.0}, self.temp_min_c, np.inf))
            rows.append(({idx.temp[t + 1]: 1.0, idx.s_t_high[t]: -1.0}, -np.inf, self.temp_max_c))
            rows.append(({idx.soc[t + 1]: 1.0, idx.s_soc_low[t]: 1.0}, self.tes.soc_planning_min, np.inf))
            rows.append(({idx.soc[t + 1]: 1.0, idx.s_soc_high[t]: -1.0}, -np.inf, self.tes.soc_planning_max))

            balance_rhs = float(forecast.base_facility_kw[t]) - float(forecast.pv_forecast_kw[t])
            rows.append(
                (
                    {
                        idx.grid[t]: 1.0,
                        idx.spill[t]: -1.0,
                        idx.q_ch[t]: -1.0 / self.facility.cop_charge,
                        idx.q_dis[t]: 1.0 / self.facility.cop_discharge_equiv,
                    },
                    balance_rhs,
                    balance_rhs,
                )
            )

            if t == 0:
                prev_ch_terms: dict[int, float] = {}
                prev_dis_terms: dict[int, float] = {}
                prev_ch = state.prev_q_ch_tes_kw_th
                prev_dis = state.prev_q_dis_tes_kw_th
            else:
                prev_ch_terms = {idx.q_ch[t - 1]: -1.0}
                prev_dis_terms = {idx.q_dis[t - 1]: -1.0}
                prev_ch = 0.0
                prev_dis = 0.0
            rows.append(({idx.q_ch[t]: 1.0, idx.du_ch[t]: -1.0, **prev_ch_terms}, -np.inf, prev_ch))
            rows.append(({idx.q_ch[t]: -1.0, idx.du_ch[t]: -1.0, **{k: -v for k, v in prev_ch_terms.items()}}, -np.inf, -prev_ch))
            rows.append(({idx.q_dis[t]: 1.0, idx.du_dis[t]: -1.0, **prev_dis_terms}, -np.inf, prev_dis))
            rows.append(({idx.q_dis[t]: -1.0, idx.du_dis[t]: -1.0, **{k: -v for k, v in prev_dis_terms.items()}}, -np.inf, -prev_dis))

        rows.append(({idx.soc[n]: 1.0, idx.s_terminal_high[0]: -1.0}, -np.inf, self.tes.soc_target))
        rows.append(({idx.soc[n]: -1.0, idx.s_terminal_low[0]: -1.0}, -np.inf, -self.tes.soc_target))

        a = lil_matrix((len(rows), idx.total), dtype=float)
        lower = np.empty(len(rows), dtype=float)
        upper = np.empty(len(rows), dtype=float)
        for r, (coefs, lo, hi) in enumerate(rows):
            for col, value in coefs.items():
                a[r, col] = value
            lower[r] = lo
            upper[r] = hi

        start = time.perf_counter()
        res = milp(
            c=c,
            integrality=integrality,
            bounds=Bounds(lb, ub),
            constraints=LinearConstraint(a.tocsr(), lower, upper),
            options={"time_limit": self.solver.time_limit_s, "mip_rel_gap": self.solver.mip_rel_gap},
        )
        elapsed = time.perf_counter() - start
        status = _status_name(int(res.status))
        if res.x is None:
            raise RuntimeError(f"MPC MILP failed without a solution: status={status}, message={res.message}")
        x = np.asarray(res.x, dtype=float)
        return MPCSolution(
            status=status,
            success=bool(res.success),
            objective_value=float(res.fun) if res.fun is not None else float("nan"),
            solve_time_s=elapsed,
            mip_gap=float(getattr(res, "mip_gap", np.nan)) if getattr(res, "mip_gap", None) is not None else None,
            q_ch_tes_kw_th=x[idx.q_ch],
            q_dis_tes_kw_th=x[idx.q_dis],
            soc=x[idx.soc],
            room_temp_c=x[idx.temp],
            grid_import_kw=x[idx.grid],
            pv_spill_kw=x[idx.spill],
            s_temp_low=x[idx.s_t_low],
            s_temp_high=x[idx.s_t_high],
            s_soc_low=x[idx.s_soc_low],
            s_soc_high=x[idx.s_soc_high],
            du_ch=x[idx.du_ch],
            du_dis=x[idx.du_dis],
            s_terminal_low=float(x[idx.s_terminal_low][0]),
            s_terminal_high=float(x[idx.s_terminal_high][0]),
        )


class _Index:
    """Flat vector slices for scipy.optimize.milp."""

    def __init__(self, n: int):
        cursor = 0
        self.q_ch = np.arange(cursor, cursor + n); cursor += n
        self.q_dis = np.arange(cursor, cursor + n); cursor += n
        self.soc = np.arange(cursor, cursor + n + 1); cursor += n + 1
        self.temp = np.arange(cursor, cursor + n + 1); cursor += n + 1
        self.grid = np.arange(cursor, cursor + n); cursor += n
        self.spill = np.arange(cursor, cursor + n); cursor += n
        self.s_t_low = np.arange(cursor, cursor + n); cursor += n
        self.s_t_high = np.arange(cursor, cursor + n); cursor += n
        self.s_soc_low = np.arange(cursor, cursor + n); cursor += n
        self.s_soc_high = np.arange(cursor, cursor + n); cursor += n
        self.z_ch = np.arange(cursor, cursor + n); cursor += n
        self.z_dis = np.arange(cursor, cursor + n); cursor += n
        self.du_ch = np.arange(cursor, cursor + n); cursor += n
        self.du_dis = np.arange(cursor, cursor + n); cursor += n
        self.s_terminal_low = np.arange(cursor, cursor + 1); cursor += 1
        self.s_terminal_high = np.arange(cursor, cursor + 1); cursor += 1
        self.total = cursor


def _status_name(status_code: int) -> str:
    return {
        0: "optimal",
        1: "time_limit",
        2: "infeasible",
        3: "unbounded",
        4: "solver_error",
    }.get(status_code, f"unknown_{status_code}")
