"""MILP construction and HiGHS solve path for economic TES MPC."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import numpy as np

from mpc_v2.core.io_schemas import ForecastBundle, SolverUnavailableError
from mpc_v2.core.pue_model import PUEParams
from mpc_v2.core.room_model import RoomParams
from mpc_v2.core.tes_model import TESParams


@dataclass(frozen=True)
class ObjectiveWeights:
    """Linear objective weights for the economic MPC."""

    c_spill: float
    c_cycle: float
    rho_T: float
    rho_soc: float
    rho_switch: float
    rho_terminal: float

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "ObjectiveWeights":
        return cls(**{field: float(config[field]) for field in cls.__dataclass_fields__})


@dataclass(frozen=True)
class SolverConfig:
    """HiGHS MILP options."""

    name: str = "highs"
    time_limit_s: float = 30.0
    mip_rel_gap: float = 0.001

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "SolverConfig":
        return cls(
            name=str(config.get("name", "highs")),
            time_limit_s=float(config.get("time_limit_s", 30.0)),
            mip_rel_gap=float(config.get("mip_rel_gap", 0.001)),
        )


@dataclass(frozen=True)
class MPCState:
    """Current state passed to the rolling MILP."""

    room_temperature_C: float
    tes_soc: float
    previous_net_action_kw: float = 0.0


@dataclass(frozen=True)
class MPCSolution:
    """Parsed MILP solution."""

    status: str
    success: bool
    objective_value: float
    solve_time_s: float
    mip_gap: float | None
    q_ch: np.ndarray
    q_dis: np.ndarray
    soc: np.ndarray
    room_temperature_C: np.ndarray
    P_grid: np.ndarray
    P_spill: np.ndarray
    eps_T_hi: np.ndarray
    eps_T_lo: np.ndarray
    eps_soc: np.ndarray
    abs_action_change: np.ndarray
    terminal_soc_slack: float

    def first_action(self) -> dict[str, float]:
        """Return the first receding-horizon TES action."""

        q_ch0 = float(max(0.0, self.q_ch[0]))
        q_dis0 = float(max(0.0, self.q_dis[0]))
        if q_ch0 < 1e-6:
            q_ch0 = 0.0
        if q_dis0 < 1e-6:
            q_dis0 = 0.0
        return {
            "tes_signed_target": q_ch0 - q_dis0,
            "tes_charge_kwth": q_ch0,
            "tes_discharge_kwth": q_dis0,
        }


class EconomicMPCProblem:
    """Build and solve the linear MILP required by the v2 plan."""

    def __init__(
        self,
        tes: TESParams,
        room: RoomParams,
        pue: PUEParams,
        weights: ObjectiveWeights,
        solver: SolverConfig,
        dt_h: float = 0.25,
    ):
        if abs(dt_h - 0.25) > 1e-9:
            raise ValueError(f"EconomicMPCProblem requires dt_h=0.25, got {dt_h}")
        if solver.name.lower() != "highs":
            raise SolverUnavailableError(f"only HiGHS is supported in v2, requested {solver.name}")
        tes.validate()
        room.validate()
        pue.validate()
        self.tes = tes
        self.room = room
        self.pue = pue
        self.weights = weights
        self.solver = solver
        self.dt_h = dt_h

    def solve(self, state: MPCState, forecast: ForecastBundle) -> MPCSolution:
        """Solve the current 48-hour economic MPC MILP with scipy/HiGHS."""

        try:
            from scipy.optimize import Bounds, LinearConstraint, milp
            from scipy.sparse import lil_matrix
        except Exception as exc:  # pragma: no cover - exercised only without scipy
            raise SolverUnavailableError("scipy.optimize.milp/HiGHS is required for MPC v2") from exc

        n = len(forecast.price_usd_per_mwh)
        forecast.validate(horizon_steps=n, dt_h=self.dt_h)
        idx = _Index(n)
        c = np.zeros(idx.total)
        lb = np.zeros(idx.total)
        ub = np.full(idx.total, np.inf)
        integrality = np.zeros(idx.total)

        # Variable bounds.
        ub[idx.q_ch] = self.tes.max_charge_kw
        ub[idx.q_dis] = self.tes.max_discharge_kw
        lb[idx.soc] = self.tes.soc_min_phys
        ub[idx.soc] = self.tes.soc_max_phys
        lb[idx.temp] = -100.0
        ub[idx.temp] = 100.0
        ub[idx.z_ch] = 1.0
        ub[idx.z_dis] = 1.0
        integrality[idx.z_ch] = 1
        integrality[idx.z_dis] = 1

        # Objective:
        # sum(price[t] * P_grid[t] * dt_h / 1000)
        # + c_spill*P_spill*dt_h
        # + c_cycle*(q_ch+q_dis)*dt_h
        # + rho_T*(eps_T_hi+eps_T_lo)
        # + rho_soc*eps_soc
        # + rho_switch*abs_action_change
        # + rho_terminal*terminal_soc_slack
        price = np.asarray(forecast.price_usd_per_mwh, dtype=float)
        c[idx.P_grid] = price * self.dt_h / 1000.0
        c[idx.P_spill] = self.weights.c_spill * self.dt_h
        c[idx.q_ch] = self.weights.c_cycle * self.dt_h
        c[idx.q_dis] = self.weights.c_cycle * self.dt_h
        c[idx.eps_hi] = self.weights.rho_T
        c[idx.eps_lo] = self.weights.rho_T
        c[idx.eps_soc] = self.weights.rho_soc
        c[idx.switch_abs] = self.weights.rho_switch
        c[idx.terminal_slack] = self.weights.rho_terminal

        rows: list[tuple[dict[int, float], float, float]] = []

        # Initial state equalities.
        rows.append(({idx.soc[0]: 1.0}, state.tes_soc, state.tes_soc))
        rows.append(({idx.temp[0]: 1.0}, state.room_temperature_C, state.room_temperature_C))

        loss_factor = 1.0 - self.tes.standing_loss_per_h * self.dt_h
        ch_gain = self.tes.charge_efficiency * self.dt_h / self.tes.effective_capacity_kwh
        dis_gain = self.dt_h / (self.tes.discharge_efficiency * self.tes.effective_capacity_kwh)
        temp_a = 1.0 - self.dt_h * self.room.outdoor_gain_fraction / self.room.thermal_time_constant_h
        temp_out_gain = self.dt_h * self.room.outdoor_gain_fraction / self.room.thermal_time_constant_h
        heat_gain = self.room.ite_heat_gain_C_per_mwh * self.dt_h / 1000.0
        cooling_gain = self.room.cooling_gain_C_per_mwh * self.dt_h / 1000.0
        ch_kw_to_facility = 1.0 / self.pue.charge_cop
        dis_kw_to_credit = 1.0 / self.pue.discharge_power_credit_cop

        for t in range(n):
            # TES SOC dynamics.
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

            # Room temperature proxy dynamics.
            rhs = (
                temp_out_gain * float(forecast.outdoor_drybulb_C[t])
                + heat_gain * float(forecast.ite_power_kw[t])
                - cooling_gain * float(forecast.base_cooling_kw[t])
            )
            rows.append(
                (
                    {
                        idx.temp[t + 1]: 1.0,
                        idx.temp[t]: -temp_a,
                        idx.q_dis[t]: cooling_gain,
                    },
                    rhs,
                    rhs,
                )
            )

            # Charge/discharge mode exclusivity.
            rows.append(({idx.q_ch[t]: 1.0, idx.z_ch[t]: -self.tes.max_charge_kw}, -np.inf, 0.0))
            rows.append(({idx.q_dis[t]: 1.0, idx.z_dis[t]: -self.tes.max_discharge_kw}, -np.inf, 0.0))
            rows.append(({idx.z_ch[t]: 1.0, idx.z_dis[t]: 1.0}, -np.inf, 1.0))

            # Temperature soft constraints.
            rows.append(({idx.temp[t + 1]: 1.0, idx.eps_hi[t]: -1.0}, -np.inf, 27.0))
            rows.append(({idx.temp[t + 1]: 1.0, idx.eps_lo[t]: 1.0}, 18.0, np.inf))

            # SOC planning soft band. Physical bounds are variable bounds.
            rows.append(({idx.soc[t + 1]: 1.0, idx.eps_soc[t]: -1.0}, -np.inf, self.tes.soc_max_plan))
            rows.append(({idx.soc[t + 1]: 1.0, idx.eps_soc[t]: 1.0}, self.tes.soc_min_plan, np.inf))

            # Power balance: P_grid - P_spill = base_facility + q_ch/COP - q_dis/COP - PV.
            balance_rhs = float(forecast.base_facility_kw[t]) - float(forecast.pv_kw[t])
            rows.append(
                (
                    {
                        idx.P_grid[t]: 1.0,
                        idx.P_spill[t]: -1.0,
                        idx.q_ch[t]: -ch_kw_to_facility,
                        idx.q_dis[t]: dis_kw_to_credit,
                    },
                    balance_rhs,
                    balance_rhs,
                )
            )

            # Absolute change in signed action q_ch - q_dis.
            if t == 0:
                prev_terms: dict[int, float] = {}
                prev_value = float(state.previous_net_action_kw)
            else:
                prev_terms = {idx.q_ch[t - 1]: -1.0, idx.q_dis[t - 1]: 1.0}
                prev_value = 0.0
            current = {idx.q_ch[t]: 1.0, idx.q_dis[t]: -1.0, idx.switch_abs[t]: -1.0}
            rows.append(({**current, **prev_terms}, -np.inf, prev_value))
            current_neg = {idx.q_ch[t]: -1.0, idx.q_dis[t]: 1.0, idx.switch_abs[t]: -1.0}
            neg_prev_terms = {k: -v for k, v in prev_terms.items()}
            rows.append(({**current_neg, **neg_prev_terms}, -np.inf, -prev_value))

        rows.append(({idx.soc[n]: 1.0, idx.terminal_slack[0]: -1.0}, -np.inf, self.tes.terminal_soc_target))
        rows.append(({idx.soc[n]: 1.0, idx.terminal_slack[0]: 1.0}, self.tes.terminal_soc_target, np.inf))

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
        status = _status_name(res.status)
        if res.x is None:
            raise RuntimeError(f"MPC MILP failed without a solution: status={status}, message={res.message}")
        x = np.asarray(res.x, dtype=float)
        return MPCSolution(
            status=status,
            success=bool(res.success),
            objective_value=float(res.fun) if res.fun is not None else float("nan"),
            solve_time_s=elapsed,
            mip_gap=float(getattr(res, "mip_gap", np.nan)) if getattr(res, "mip_gap", None) is not None else None,
            q_ch=x[idx.q_ch],
            q_dis=x[idx.q_dis],
            soc=x[idx.soc],
            room_temperature_C=x[idx.temp],
            P_grid=x[idx.P_grid],
            P_spill=x[idx.P_spill],
            eps_T_hi=x[idx.eps_hi],
            eps_T_lo=x[idx.eps_lo],
            eps_soc=x[idx.eps_soc],
            abs_action_change=x[idx.switch_abs],
            terminal_soc_slack=float(x[idx.terminal_slack][0]),
        )


class _Index:
    """Column slices for the flat MILP vector."""

    def __init__(self, n: int):
        cursor = 0
        self.q_ch = np.arange(cursor, cursor + n); cursor += n
        self.q_dis = np.arange(cursor, cursor + n); cursor += n
        self.soc = np.arange(cursor, cursor + n + 1); cursor += n + 1
        self.temp = np.arange(cursor, cursor + n + 1); cursor += n + 1
        self.P_grid = np.arange(cursor, cursor + n); cursor += n
        self.P_spill = np.arange(cursor, cursor + n); cursor += n
        self.eps_hi = np.arange(cursor, cursor + n); cursor += n
        self.eps_lo = np.arange(cursor, cursor + n); cursor += n
        self.eps_soc = np.arange(cursor, cursor + n); cursor += n
        self.z_ch = np.arange(cursor, cursor + n); cursor += n
        self.z_dis = np.arange(cursor, cursor + n); cursor += n
        self.switch_abs = np.arange(cursor, cursor + n); cursor += n
        self.terminal_slack = np.arange(cursor, cursor + 1); cursor += 1
        self.total = cursor


def _status_name(status_code: int) -> str:
    return {
        0: "optimal",
        1: "time_limit",
        2: "infeasible",
        3: "unbounded",
        4: "solver_error",
    }.get(int(status_code), f"unknown_{status_code}")

