"""Minimal deterministic controllers for the rebuilt MPC v1 path."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from scipy.optimize import linprog

from mpc_v2.core.io_schemas import ForecastBundle, MPCAction, MPCState, SolverUnavailableError
from mpc_v2.core.plant import PlantParams, chiller_power_kw, grid_and_spill_kw
from mpc_v2.core.tes_model import TESModel, TESParams


@dataclass(frozen=True)
class MPCSolution:
    """Full-horizon controller output used by the simulator."""

    status: str
    objective_value: float
    q_ch_tes_kw_th: np.ndarray
    q_dis_tes_kw_th: np.ndarray
    q_chiller_kw_th: np.ndarray
    q_load_kw_th: np.ndarray
    plant_power_kw: np.ndarray
    grid_import_kw: np.ndarray
    pv_spill_kw: np.ndarray
    soc: np.ndarray
    q_ch_max_kw_th: float
    q_dis_max_kw_th: float
    fallback: bool = False

    @property
    def u_ch(self) -> np.ndarray:
        return self.q_ch_tes_kw_th / max(self.q_ch_max_kw_th, 1e-9)

    @property
    def u_dis(self) -> np.ndarray:
        return self.q_dis_tes_kw_th / max(self.q_dis_max_kw_th, 1e-9)

    def first_action(self, tes: TESParams) -> MPCAction:
        q_ch = float(self.q_ch_tes_kw_th[0])
        q_dis = float(self.q_dis_tes_kw_th[0])
        action = MPCAction(
            q_ch_tes_kw_th=q_ch,
            q_dis_tes_kw_th=q_dis,
            q_chiller_kw_th=float(self.q_chiller_kw_th[0]),
            q_load_kw_th=float(self.q_load_kw_th[0]),
            plant_power_kw=float(self.plant_power_kw[0]),
            u_ch=q_ch / tes.q_ch_max_kw_th if tes.q_ch_max_kw_th > 0 else 0.0,
            u_dis=q_dis / tes.q_dis_max_kw_th if tes.q_dis_max_kw_th > 0 else 0.0,
            mode_index=0,
            q_ch_max_kw_th=tes.q_ch_max_kw_th,
            q_dis_max_kw_th=tes.q_dis_max_kw_th,
        )
        action.validate()
        return action


class NoTESController:
    """Baseline controller that serves cooling directly and never uses TES."""

    def __init__(self, tes: TESParams, plant: PlantParams, dt_hours: float):
        self.tes = tes
        self.plant = plant
        self.dt_hours = float(dt_hours)

    @classmethod
    def from_config(cls, cfg: dict[str, Any]) -> "NoTESController":
        return cls(
            TESParams.from_config(cfg["tes"]),
            PlantParams.from_config(cfg),
            float(cfg["time"]["dt_hours"]),
        )

    def solve(self, state: MPCState, forecast: ForecastBundle, tes_available: bool = False) -> MPCSolution:
        forecast.validate(len(forecast.timestamps), self.dt_hours)
        load = np.asarray(forecast.base_cooling_kw_th, dtype=float)
        q_ch = np.zeros_like(load)
        q_dis = np.zeros_like(load)
        return build_deterministic_solution(state, forecast, self.tes, self.plant, self.dt_hours, q_ch, q_dis, "optimal")


class RuleBasedTESController(NoTESController):
    """Simple price-threshold baseline for charge/discharge behavior."""

    def solve(self, state: MPCState, forecast: ForecastBundle, tes_available: bool = True) -> MPCSolution:
        forecast.validate(len(forecast.timestamps), self.dt_hours)
        if not tes_available:
            return super().solve(state, forecast, tes_available=False)
        prices = np.asarray(forecast.price_forecast, dtype=float)
        load = np.asarray(forecast.base_cooling_kw_th, dtype=float)
        q_ch = np.zeros_like(load)
        q_dis = np.zeros_like(load)
        low = float(np.quantile(prices, 0.30))
        high = float(np.quantile(prices, 0.70))
        model = TESModel(self.tes, self.dt_hours)
        soc = float(state.soc)
        for i, price in enumerate(prices):
            if price <= low and soc < self.tes.soc_planning_max - 1e-6:
                max_charge = (self.tes.soc_planning_max - soc) * self.tes.capacity_kwh_th
                max_charge /= max(self.tes.eta_ch * self.dt_hours, 1e-9)
                q_ch[i] = min(self.tes.q_ch_max_kw_th, max_charge)
            elif price >= high and soc > self.tes.soc_planning_min + 1e-6:
                max_dis = (soc - self.tes.soc_planning_min) * self.tes.capacity_kwh_th
                max_dis *= self.tes.eta_dis / max(self.dt_hours, 1e-9)
                q_dis[i] = min(self.tes.q_dis_max_kw_th, max_dis, load[i])
            soc = model.next_soc(soc, float(q_ch[i]), float(q_dis[i]))
        return build_deterministic_solution(state, forecast, self.tes, self.plant, self.dt_hours, q_ch, q_dis, "optimal")


class EconomicTESMPCController(NoTESController):
    """Linear deterministic MPC with SOC dynamics and terminal SOC target."""

    def __init__(
        self,
        tes: TESParams,
        plant: PlantParams,
        dt_hours: float,
        w_terminal: float,
        w_cycle: float,
        w_spill: float,
    ):
        super().__init__(tes, plant, dt_hours)
        self.w_terminal = float(w_terminal)
        self.w_cycle = float(w_cycle)
        self.w_spill = float(w_spill)

    @classmethod
    def from_config(cls, cfg: dict[str, Any]) -> "EconomicTESMPCController":
        objective = cfg.get("objective", {})
        return cls(
            TESParams.from_config(cfg["tes"]),
            PlantParams.from_config(cfg),
            float(cfg["time"]["dt_hours"]),
            float(objective.get("w_terminal", 50000.0)),
            float(objective.get("w_cycle", 0.001)),
            float(objective.get("w_spill", 0.02)),
        )

    def solve(self, state: MPCState, forecast: ForecastBundle, tes_available: bool = True) -> MPCSolution:
        forecast.validate(len(forecast.timestamps), self.dt_hours)
        if not tes_available:
            return super().solve(state, forecast, tes_available=False)
        try:
            return self._solve_lp(state, forecast)
        except Exception as exc:  # pragma: no cover - defensive fallback path
            if isinstance(exc, SolverUnavailableError):
                raise
            fallback = RuleBasedTESController(self.tes, self.plant, self.dt_hours).solve(state, forecast)
            return MPCSolution(
                status=f"fallback:{type(exc).__name__}",
                objective_value=fallback.objective_value,
                q_ch_tes_kw_th=fallback.q_ch_tes_kw_th,
                q_dis_tes_kw_th=fallback.q_dis_tes_kw_th,
                q_chiller_kw_th=fallback.q_chiller_kw_th,
                q_load_kw_th=fallback.q_load_kw_th,
                plant_power_kw=fallback.plant_power_kw,
                grid_import_kw=fallback.grid_import_kw,
                pv_spill_kw=fallback.pv_spill_kw,
                soc=fallback.soc,
                q_ch_max_kw_th=fallback.q_ch_max_kw_th,
                q_dis_max_kw_th=fallback.q_dis_max_kw_th,
                fallback=True,
            )

    def _solve_lp(self, state: MPCState, forecast: ForecastBundle) -> MPCSolution:
        horizon = len(forecast.timestamps)
        load = np.asarray(forecast.base_cooling_kw_th, dtype=float)
        it_load = np.asarray(forecast.it_load_forecast_kw, dtype=float)
        pv = np.asarray(forecast.pv_forecast_kw, dtype=float)
        price = np.asarray(forecast.price_forecast, dtype=float)
        cop = max(self.plant.cop, 1e-9)
        tes = self.tes
        dt = self.dt_hours

        qch0 = 0
        qdis0 = horizon
        soc0 = 2 * horizon
        grid0 = soc0 + horizon + 1
        spill0 = grid0 + horizon
        term_pos = spill0 + horizon
        term_neg = term_pos + 1
        nvar = term_neg + 1

        c = np.zeros(nvar)
        c[qch0 : qch0 + horizon] = self.w_cycle * dt
        c[qdis0 : qdis0 + horizon] = self.w_cycle * dt
        c[grid0 : grid0 + horizon] = price * dt
        c[spill0 : spill0 + horizon] = self.w_spill * dt
        c[term_pos] = self.w_terminal
        c[term_neg] = self.w_terminal

        bounds: list[tuple[float, float | None]] = []
        bounds.extend((0.0, tes.q_ch_max_kw_th) for _ in range(horizon))
        bounds.extend((0.0, min(tes.q_dis_max_kw_th, float(v))) for v in load)
        bounds.append((float(state.soc), float(state.soc)))
        bounds.extend((tes.soc_planning_min, tes.soc_planning_max) for _ in range(horizon))
        bounds.extend((0.0, None) for _ in range(horizon))
        bounds.extend((0.0, None) for _ in range(horizon))
        bounds.append((0.0, None))
        bounds.append((0.0, None))

        a_eq: list[np.ndarray] = []
        b_eq: list[float] = []

        decay = 1.0 - tes.lambda_loss_per_h * dt
        charge_gain = tes.eta_ch * dt / tes.capacity_kwh_th
        discharge_loss = dt / (tes.eta_dis * tes.capacity_kwh_th)
        for t in range(horizon):
            row = np.zeros(nvar)
            row[soc0 + t + 1] = 1.0
            row[soc0 + t] = -decay
            row[qch0 + t] = -charge_gain
            row[qdis0 + t] = discharge_loss
            a_eq.append(row)
            b_eq.append(0.0)

        for t in range(horizon):
            row = np.zeros(nvar)
            row[grid0 + t] = 1.0
            row[spill0 + t] = -1.0
            row[qch0 + t] = -1.0 / cop
            row[qdis0 + t] = 1.0 / cop
            a_eq.append(row)
            b_eq.append(float(it_load[t] + load[t] / cop - pv[t]))

        row = np.zeros(nvar)
        row[soc0 + horizon] = 1.0
        row[term_pos] = -1.0
        row[term_neg] = 1.0
        a_eq.append(row)
        b_eq.append(tes.soc_target)

        result = linprog(
            c,
            A_eq=np.asarray(a_eq),
            b_eq=np.asarray(b_eq),
            bounds=bounds,
            method="highs",
        )
        if not result.success:
            raise SolverUnavailableError(f"linear MPC solve failed: {result.message}")
        x = np.asarray(result.x, dtype=float)
        q_ch = _clean_small(x[qch0 : qch0 + horizon])
        q_dis = _clean_small(x[qdis0 : qdis0 + horizon])
        return build_deterministic_solution(
            state,
            forecast,
            tes,
            self.plant,
            self.dt_hours,
            q_ch,
            q_dis,
            "optimal",
            float(result.fun),
        )


def build_deterministic_solution(
    state: MPCState,
    forecast: ForecastBundle,
    tes: TESParams,
    plant: PlantParams,
    dt_hours: float,
    q_ch: np.ndarray,
    q_dis: np.ndarray,
    status: str,
    objective_value: float | None = None,
) -> MPCSolution:
    """Build a consistent horizon solution from charge/discharge profiles."""

    load = np.asarray(forecast.base_cooling_kw_th, dtype=float)
    it_load = np.asarray(forecast.it_load_forecast_kw, dtype=float)
    pv = np.asarray(forecast.pv_forecast_kw, dtype=float)
    q_ch = _clean_small(np.asarray(q_ch, dtype=float))
    q_dis = _clean_small(np.asarray(q_dis, dtype=float))
    q_dis = np.minimum(q_dis, load)
    q_load = np.maximum(0.0, load - q_dis)
    q_chiller = q_load + q_ch
    plant_power = np.asarray([chiller_power_kw(v, plant) for v in q_chiller], dtype=float)
    grid = np.zeros_like(load)
    spill = np.zeros_like(load)
    for i, (it, plant_kw, pv_kw) in enumerate(zip(it_load, plant_power, pv)):
        grid[i], spill[i] = grid_and_spill_kw(float(it), float(plant_kw), float(pv_kw))
    model = TESModel(tes, dt_hours)
    soc = [float(state.soc)]
    for ch, dis in zip(q_ch, q_dis):
        soc.append(model.next_soc(soc[-1], float(ch), float(dis)))
    value = float(objective_value if objective_value is not None else np.dot(grid, forecast.price_forecast) * dt_hours)
    return MPCSolution(
        status=status,
        objective_value=value,
        q_ch_tes_kw_th=q_ch,
        q_dis_tes_kw_th=q_dis,
        q_chiller_kw_th=q_chiller,
        q_load_kw_th=q_load,
        plant_power_kw=plant_power,
        grid_import_kw=grid,
        pv_spill_kw=spill,
        soc=np.asarray(soc, dtype=float),
        q_ch_max_kw_th=tes.q_ch_max_kw_th,
        q_dis_max_kw_th=tes.q_dis_max_kw_th,
        fallback=status != "optimal",
    )


def controller_from_mode(mode: str, cfg: dict[str, Any]) -> tuple[NoTESController, bool]:
    """Return controller instance and TES availability for a public mode name."""

    normalized = mode.strip().lower()
    if normalized in {"no_tes", "mpc_no_tes"}:
        return NoTESController.from_config(cfg), False
    if normalized == "rbc":
        return RuleBasedTESController.from_config(cfg), True
    if normalized == "mpc":
        return EconomicTESMPCController.from_config(cfg), True
    raise ValueError(f"unsupported controller_mode: {mode}")


def _clean_small(values: np.ndarray) -> np.ndarray:
    out = np.asarray(values, dtype=float).copy()
    out[np.abs(out) < 1e-7] = 0.0
    return out
