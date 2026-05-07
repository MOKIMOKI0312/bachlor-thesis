"""MILP construction and HiGHS solve path for chiller+TES MPC."""

from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any

import numpy as np

from mpc_v2.core.facility_model import ChillerPlantParams, EconomicsParams, FacilityParams, ValveParams
from mpc_v2.core.io_schemas import ForecastBundle, MPCAction, MPCState, SolverUnavailableError
from mpc_v2.core.room_model import RoomParams
from mpc_v2.core.tes_model import TESParams


@dataclass(frozen=True)
class ObjectiveWeights:
    """Linear objective weights."""

    w_spill: float = 0.02
    w_cycle: float = 0.001
    w_temp: float = 1000.0
    w_soc: float = 200.0
    w_switch: float = 0.0005
    w_terminal: float = 100.0
    w_valve: float = 0.05
    w_plr: float = 0.0
    w_start: float = 0.0
    w_demand: float = 1.0
    w_peak_slack: float = 50000.0

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "ObjectiveWeights":
        values = {field: float(config.get(field, getattr(cls, field))) for field in cls.__dataclass_fields__}
        if "w_valve" not in config and "w_switch" in config:
            values["w_valve"] = float(config["w_switch"])
        return cls(**values)


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
    q_chiller_kw_th: np.ndarray
    q_load_kw_th: np.ndarray
    plant_power_kw: np.ndarray
    mode_binary: np.ndarray
    delta_on: np.ndarray
    delta_off: np.ndarray
    u_ch: np.ndarray
    u_dis: np.ndarray
    u_signed: np.ndarray
    soc: np.ndarray
    room_temp_c: np.ndarray
    grid_import_kw: np.ndarray
    pv_spill_kw: np.ndarray
    peak_grid_kw: float
    s_temp_low: np.ndarray
    s_temp_high: np.ndarray
    s_soc_low: np.ndarray
    s_soc_high: np.ndarray
    du_ch: np.ndarray
    du_dis: np.ndarray
    du_signed: np.ndarray
    xi_low_plr: np.ndarray
    s_peak: np.ndarray
    s_terminal_low: float
    s_terminal_high: float
    q_ch_max_kw_th: float
    q_dis_max_kw_th: float

    def first_action(self) -> MPCAction:
        q_ch = _clean_power(self.q_ch_tes_kw_th[0])
        q_dis = _clean_power(self.q_dis_tes_kw_th[0])
        q_chiller = _clean_power(self.q_chiller_kw_th[0])
        q_load = _clean_power(self.q_load_kw_th[0])
        plant_power = _clean_power(self.plant_power_kw[0])
        mode_index = self.mode_index_at(0)
        u_ch = _clean_fraction(q_ch / self.q_ch_max_kw_th)
        u_dis = _clean_fraction(q_dis / self.q_dis_max_kw_th)
        return MPCAction(
            q_ch_tes_kw_th=q_ch,
            q_dis_tes_kw_th=q_dis,
            q_chiller_kw_th=q_chiller,
            q_load_kw_th=q_load,
            plant_power_kw=plant_power,
            u_ch=u_ch,
            u_dis=u_dis,
            mode_index=mode_index,
            q_ch_max_kw_th=self.q_ch_max_kw_th,
            q_dis_max_kw_th=self.q_dis_max_kw_th,
        )

    def mode_index_at(self, step: int) -> int:
        if self.mode_binary.shape[0] == 0:
            return -1
        column = self.mode_binary[:, step]
        if float(column.max(initial=0.0)) < 0.5:
            return -1
        return int(np.argmax(column))


class EconomicMPCProblem:
    """Build and solve the deterministic chiller+TES MILP."""

    def __init__(
        self,
        tes: TESParams,
        room: RoomParams,
        facility: FacilityParams,
        chiller: ChillerPlantParams,
        valve: ValveParams,
        economics: EconomicsParams,
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
        chiller.validate()
        valve.validate()
        economics.validate()
        if temp_min_c >= temp_max_c:
            raise ValueError("temp_min_c must be below temp_max_c")
        self.tes = tes
        self.room = room
        self.facility = facility
        self.chiller = chiller
        self.valve = valve
        self.economics = economics
        self.weights = weights
        self.solver = solver
        self.temp_min_c = float(temp_min_c)
        self.temp_max_c = float(temp_max_c)
        self.dt_hours = float(dt_hours)

    def solve(self, state: MPCState, forecast: ForecastBundle, tes_available: bool = True) -> MPCSolution:
        """Solve the current receding-horizon MILP."""

        try:
            from scipy.optimize import Bounds, LinearConstraint, milp
            from scipy.sparse import lil_matrix
        except Exception as exc:  # pragma: no cover
            raise SolverUnavailableError("scipy.optimize.milp/HiGHS is required") from exc

        state.validate()
        n = len(forecast.price_forecast)
        forecast.validate(horizon_steps=n, dt_hours=self.dt_hours)
        idx = _Index(n, len(self.chiller.modes))
        c = np.zeros(idx.total)
        lb = np.zeros(idx.total)
        ub = np.full(idx.total, np.inf)
        integrality = np.zeros(idx.total)

        ub[idx.q_ch] = self.tes.q_ch_max_kw_th if tes_available else 0.0
        ub[idx.q_dis] = self.tes.q_dis_max_kw_th if tes_available else 0.0
        ub[idx.q_chiller] = self.chiller.q_max_kw_th
        ub[idx.q_load] = self.chiller.q_max_kw_th
        ub[idx.nu] = np.array([[mode.q_max_kw_th] * n for mode in self.chiller.modes])
        ub[idx.u_ch] = self.valve.u_max if tes_available else 0.0
        ub[idx.u_dis] = self.valve.u_max if tes_available else 0.0
        lb[idx.u_ch] = self.valve.u_min if tes_available else 0.0
        lb[idx.u_dis] = self.valve.u_min if tes_available else 0.0
        lb[idx.u_signed] = -self.valve.u_max if tes_available else 0.0
        ub[idx.u_signed] = self.valve.u_max if tes_available else 0.0
        ub[idx.du_ch] = self.valve.du_max_per_step
        ub[idx.du_dis] = self.valve.du_max_per_step
        ub[idx.du_signed] = self.valve.du_signed_max_per_step
        lb[idx.soc] = self.tes.soc_physical_min
        ub[idx.soc] = self.tes.soc_physical_max
        lb[idx.temp] = -100.0
        ub[idx.temp] = 100.0
        ub[idx.z_mode] = 1.0
        ub[idx.delta_on] = 1.0
        ub[idx.delta_off] = 1.0
        integrality[idx.z_mode] = 1
        integrality[idx.delta_on] = 1
        integrality[idx.delta_off] = 1

        price = np.asarray(forecast.price_forecast, dtype=float)
        c[idx.grid] = price * self.dt_hours / 1000.0
        c[idx.spill] = self.weights.w_spill * self.dt_hours
        c[idx.q_ch] = self.weights.w_cycle * self.dt_hours
        c[idx.q_dis] = self.weights.w_cycle * self.dt_hours
        c[idx.s_t_low] = self.weights.w_temp * self.dt_hours
        c[idx.s_t_high] = self.weights.w_temp * self.dt_hours
        c[idx.s_soc_low] = self.weights.w_soc
        c[idx.s_soc_high] = self.weights.w_soc
        c[idx.du_ch] = self.weights.w_valve
        c[idx.du_dis] = self.weights.w_valve
        c[idx.du_signed] = self.weights.w_valve
        c[idx.xi_low_plr] = self.weights.w_plr
        c[idx.delta_on] = self.weights.w_start
        c[idx.peak_grid] = self.weights.w_demand * self.economics.demand_charge_rate * self.economics.demand_charge_multiplier(n * self.dt_hours)
        c[idx.s_peak] = self.weights.w_peak_slack
        c[idx.s_terminal_low] = self.weights.w_terminal
        c[idx.s_terminal_high] = self.weights.w_terminal

        rows: list[tuple[dict[int, float], float, float]] = []
        rows.append(({int(idx.soc[0]): 1.0}, state.soc, state.soc))
        rows.append(({int(idx.temp[0]): 1.0}, state.room_temp_c, state.room_temp_c))

        dt = self.dt_hours
        loss_factor = 1.0 - self.tes.lambda_loss_per_h * dt if tes_available else 1.0
        ch_gain = self.tes.eta_ch * dt / self.tes.capacity_kwh_th
        dis_gain = dt / (self.tes.eta_dis * self.tes.capacity_kwh_th)
        temp_a = 1.0 - dt * self.room.outdoor_gain_fraction / self.room.thermal_time_constant_h
        temp_out_gain = dt * self.room.outdoor_gain_fraction / self.room.thermal_time_constant_h
        heat_gain = self.room.it_heat_gain_c_per_mwh * dt / 1000.0
        cooling_gain = self.room.cooling_gain_c_per_mwh * dt / 1000.0
        wet_bulb = np.asarray(forecast.wet_bulb_or_default(), dtype=float)
        dynamic_peak_cap = (
            np.asarray(forecast.dynamic_peak_cap_kw, dtype=float)
            if forecast.dynamic_peak_cap_kw is not None
            else None
        )

        for t in range(n):
            rows.append(
                (
                    {
                        int(idx.soc[t + 1]): 1.0,
                        int(idx.soc[t]): -loss_factor,
                        int(idx.q_ch[t]): -ch_gain,
                        int(idx.q_dis[t]): dis_gain,
                    },
                    0.0,
                    0.0,
                )
            )

            temp_rhs = (
                temp_out_gain * float(forecast.outdoor_temp_forecast_c[t])
                + heat_gain * float(forecast.it_load_forecast_kw[t])
            )
            rows.append(
                (
                    {
                        int(idx.temp[t + 1]): 1.0,
                        int(idx.temp[t]): -temp_a,
                        int(idx.q_load[t]): cooling_gain,
                        int(idx.q_dis[t]): cooling_gain,
                    },
                    temp_rhs,
                    temp_rhs,
                )
            )

            rows.append(
                (
                    {int(idx.q_chiller[t]): 1.0, int(idx.q_load[t]): -1.0, int(idx.q_ch[t]): -1.0},
                    0.0,
                    0.0,
                )
            )
            coefs = {int(idx.q_chiller[t]): 1.0}
            for m in range(idx.m):
                coefs[int(idx.nu[m, t])] = -1.0
            rows.append((coefs, 0.0, 0.0))

            rows.append(({int(idx.z_mode[m, t]): 1.0 for m in range(idx.m)}, -np.inf, 1.0))
            for m, mode in enumerate(self.chiller.modes):
                rows.append(({int(idx.nu[m, t]): 1.0, int(idx.z_mode[m, t]): -mode.q_max_kw_th}, -np.inf, 0.0))
                rows.append(({int(idx.nu[m, t]): 1.0, int(idx.z_mode[m, t]): -mode.q_min_kw_th}, 0.0, np.inf))

            for m, mode in enumerate(self.chiller.modes):
                if t == 0:
                    prev_z = 1.0 if state.prev_mode_index == m else 0.0
                    rows.append(
                        (
                            {
                                int(idx.z_mode[m, t]): 1.0,
                                int(idx.delta_on[m, t]): -1.0,
                                int(idx.delta_off[m, t]): 1.0,
                            },
                            prev_z,
                            prev_z,
                        )
                    )
                else:
                    rows.append(
                        (
                            {
                                int(idx.z_mode[m, t]): 1.0,
                                int(idx.z_mode[m, t - 1]): -1.0,
                                int(idx.delta_on[m, t]): -1.0,
                                int(idx.delta_off[m, t]): 1.0,
                            },
                            0.0,
                            0.0,
                        )
                    )
                rows.append(({int(idx.delta_on[m, t]): 1.0, int(idx.delta_off[m, t]): 1.0}, -np.inf, 1.0))
                on_window = range(max(0, t - mode.min_on_steps + 1), t + 1)
                rows.append(
                    (
                        {
                            **{int(idx.delta_on[m, j]): 1.0 for j in on_window},
                            int(idx.z_mode[m, t]): -1.0,
                        },
                        -np.inf,
                        0.0,
                    )
                )
                off_window = range(max(0, t - mode.min_off_steps + 1), t + 1)
                rows.append(
                    (
                        {
                            **{int(idx.delta_off[m, j]): 1.0 for j in off_window},
                            int(idx.z_mode[m, t]): 1.0,
                        },
                        -np.inf,
                        1.0,
                    )
                )

            plant_coefs = {int(idx.plant_power[t]): 1.0}
            for m, mode in enumerate(self.chiller.modes):
                plant_coefs[int(idx.nu[m, t])] = plant_coefs.get(int(idx.nu[m, t]), 0.0) - mode.a_kw_per_kwth
                intercept = mode.c0_kw + mode.c1_kw_per_c * float(wet_bulb[t])
                plant_coefs[int(idx.z_mode[m, t])] = plant_coefs.get(int(idx.z_mode[m, t]), 0.0) - intercept
            rows.append((plant_coefs, 0.0, 0.0))

            rows.append(({int(idx.q_ch[t]): 1.0, int(idx.u_ch[t]): -self.tes.q_ch_max_kw_th}, 0.0, 0.0))
            rows.append(({int(idx.q_dis[t]): 1.0, int(idx.u_dis[t]): -self.tes.q_dis_max_kw_th}, 0.0, 0.0))
            rows.append(({int(idx.u_ch[t]): 1.0, int(idx.u_dis[t]): 1.0}, -np.inf, 1.0))
            rows.append(
                (
                    {int(idx.u_signed[t]): 1.0, int(idx.u_ch[t]): -1.0, int(idx.u_dis[t]): 1.0},
                    0.0,
                    0.0,
                )
            )

            rows.append(({int(idx.temp[t + 1]): 1.0, int(idx.s_t_low[t]): 1.0}, self.temp_min_c, np.inf))
            rows.append(({int(idx.temp[t + 1]): 1.0, int(idx.s_t_high[t]): -1.0}, -np.inf, self.temp_max_c))
            rows.append(({int(idx.soc[t + 1]): 1.0, int(idx.s_soc_low[t]): 1.0}, self.tes.soc_planning_min, np.inf))
            rows.append(({int(idx.soc[t + 1]): 1.0, int(idx.s_soc_high[t]): -1.0}, -np.inf, self.tes.soc_planning_max))

            rows.append(
                (
                    {
                        int(idx.grid[t]): 1.0,
                        int(idx.spill[t]): -1.0,
                        int(idx.plant_power[t]): -1.0,
                    },
                    float(forecast.it_load_forecast_kw[t]) - float(forecast.pv_forecast_kw[t]),
                    float(forecast.it_load_forecast_kw[t]) - float(forecast.pv_forecast_kw[t]),
                )
            )
            rows.append(({int(idx.grid[t]): 1.0, int(idx.peak_grid[0]): -1.0}, -np.inf, 0.0))
            if dynamic_peak_cap is not None and dynamic_peak_cap[t] >= 0.0:
                rows.append(
                    (
                        {int(idx.grid[t]): 1.0, int(idx.s_peak[t]): -1.0},
                        -np.inf,
                        float(dynamic_peak_cap[t]),
                    )
                )
            elif self.economics.peak_cap_kw is not None:
                rows.append(
                    (
                        {int(idx.grid[t]): 1.0, int(idx.s_peak[t]): -1.0},
                        -np.inf,
                        float(self.economics.peak_cap_kw),
                    )
                )

            if t == 0:
                prev_u_ch_terms: dict[int, float] = {}
                prev_u_dis_terms: dict[int, float] = {}
                prev_u_signed_terms: dict[int, float] = {}
                prev_u_ch = state.prev_u_ch
                prev_u_dis = state.prev_u_dis
                prev_u_signed = state.prev_u_signed
            else:
                prev_u_ch_terms = {int(idx.u_ch[t - 1]): -1.0}
                prev_u_dis_terms = {int(idx.u_dis[t - 1]): -1.0}
                prev_u_signed_terms = {int(idx.u_signed[t - 1]): -1.0}
                prev_u_ch = 0.0
                prev_u_dis = 0.0
                prev_u_signed = 0.0
            rows.append(({int(idx.u_ch[t]): 1.0, int(idx.du_ch[t]): -1.0, **prev_u_ch_terms}, -np.inf, prev_u_ch))
            rows.append(
                (
                    {int(idx.u_ch[t]): -1.0, int(idx.du_ch[t]): -1.0, **{k: -v for k, v in prev_u_ch_terms.items()}},
                    -np.inf,
                    -prev_u_ch,
                )
            )
            rows.append(({int(idx.u_dis[t]): 1.0, int(idx.du_dis[t]): -1.0, **prev_u_dis_terms}, -np.inf, prev_u_dis))
            rows.append(
                (
                    {
                        int(idx.u_dis[t]): -1.0,
                        int(idx.du_dis[t]): -1.0,
                        **{k: -v for k, v in prev_u_dis_terms.items()},
                    },
                    -np.inf,
                    -prev_u_dis,
                )
            )
            rows.append(
                (
                    {int(idx.u_signed[t]): 1.0, int(idx.du_signed[t]): -1.0, **prev_u_signed_terms},
                    -np.inf,
                    prev_u_signed,
                )
            )
            rows.append(
                (
                    {
                        int(idx.u_signed[t]): -1.0,
                        int(idx.du_signed[t]): -1.0,
                        **{k: -v for k, v in prev_u_signed_terms.items()},
                    },
                    -np.inf,
                    -prev_u_signed,
                )
            )

            plr_coefs = {int(idx.xi_low_plr[t]): 1.0}
            for m, mode in enumerate(self.chiller.modes):
                plr_coefs[int(idx.nu[m, t])] = plr_coefs.get(int(idx.nu[m, t]), 0.0) + 1.0
                plr_coefs[int(idx.z_mode[m, t])] = (
                    plr_coefs.get(int(idx.z_mode[m, t]), 0.0) - self.chiller.plr_pref * mode.q_max_kw_th
                )
            rows.append((plr_coefs, 0.0, np.inf))

        rows.append(({int(idx.soc[n]): 1.0, int(idx.s_terminal_high[0]): -1.0}, -np.inf, self.tes.soc_target))
        rows.append(({int(idx.soc[n]): 1.0, int(idx.s_terminal_low[0]): 1.0}, self.tes.soc_target, np.inf))

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
            q_chiller_kw_th=x[idx.q_chiller],
            q_load_kw_th=x[idx.q_load],
            plant_power_kw=x[idx.plant_power],
            mode_binary=x[idx.z_mode],
            delta_on=x[idx.delta_on],
            delta_off=x[idx.delta_off],
            u_ch=x[idx.u_ch],
            u_dis=x[idx.u_dis],
            u_signed=x[idx.u_signed],
            soc=x[idx.soc],
            room_temp_c=x[idx.temp],
            grid_import_kw=x[idx.grid],
            pv_spill_kw=x[idx.spill],
            peak_grid_kw=float(x[idx.peak_grid][0]),
            s_temp_low=x[idx.s_t_low],
            s_temp_high=x[idx.s_t_high],
            s_soc_low=x[idx.s_soc_low],
            s_soc_high=x[idx.s_soc_high],
            du_ch=x[idx.du_ch],
            du_dis=x[idx.du_dis],
            du_signed=x[idx.du_signed],
            xi_low_plr=x[idx.xi_low_plr],
            s_peak=x[idx.s_peak],
            s_terminal_low=float(x[idx.s_terminal_low][0]),
            s_terminal_high=float(x[idx.s_terminal_high][0]),
            q_ch_max_kw_th=self.tes.q_ch_max_kw_th,
            q_dis_max_kw_th=self.tes.q_dis_max_kw_th,
        )


class _Index:
    """Flat vector slices for scipy.optimize.milp."""

    def __init__(self, n: int, m: int):
        self.n = n
        self.m = m
        cursor = 0
        self.q_ch = np.arange(cursor, cursor + n); cursor += n
        self.q_dis = np.arange(cursor, cursor + n); cursor += n
        self.q_chiller = np.arange(cursor, cursor + n); cursor += n
        self.q_load = np.arange(cursor, cursor + n); cursor += n
        self.plant_power = np.arange(cursor, cursor + n); cursor += n
        self.nu = np.arange(cursor, cursor + m * n).reshape(m, n); cursor += m * n
        self.z_mode = np.arange(cursor, cursor + m * n).reshape(m, n); cursor += m * n
        self.delta_on = np.arange(cursor, cursor + m * n).reshape(m, n); cursor += m * n
        self.delta_off = np.arange(cursor, cursor + m * n).reshape(m, n); cursor += m * n
        self.u_ch = np.arange(cursor, cursor + n); cursor += n
        self.u_dis = np.arange(cursor, cursor + n); cursor += n
        self.u_signed = np.arange(cursor, cursor + n); cursor += n
        self.soc = np.arange(cursor, cursor + n + 1); cursor += n + 1
        self.temp = np.arange(cursor, cursor + n + 1); cursor += n + 1
        self.grid = np.arange(cursor, cursor + n); cursor += n
        self.spill = np.arange(cursor, cursor + n); cursor += n
        self.peak_grid = np.arange(cursor, cursor + 1); cursor += 1
        self.s_t_low = np.arange(cursor, cursor + n); cursor += n
        self.s_t_high = np.arange(cursor, cursor + n); cursor += n
        self.s_soc_low = np.arange(cursor, cursor + n); cursor += n
        self.s_soc_high = np.arange(cursor, cursor + n); cursor += n
        self.du_ch = np.arange(cursor, cursor + n); cursor += n
        self.du_dis = np.arange(cursor, cursor + n); cursor += n
        self.du_signed = np.arange(cursor, cursor + n); cursor += n
        self.xi_low_plr = np.arange(cursor, cursor + n); cursor += n
        self.s_peak = np.arange(cursor, cursor + n); cursor += n
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


def _clean_power(value: float) -> float:
    value = float(max(0.0, value))
    return 0.0 if value < 1e-6 else value


def _clean_fraction(value: float) -> float:
    value = min(1.0, max(0.0, float(value)))
    return 0.0 if value < 1e-9 else value
