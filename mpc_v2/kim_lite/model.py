"""Kim-lite data preparation and paper-like MILP model."""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import replace
from datetime import datetime, timedelta
import time

import numpy as np
import pandas as pd
from scipy.optimize import Bounds, LinearConstraint, milp

from mpc_v2.kim_lite.config import KimLiteConfig, ModeConfig


@dataclass(frozen=True)
class KimLiteInputs:
    timestamps: list[datetime]
    q_load_kw_th: np.ndarray
    p_nonplant_kw: np.ndarray
    p_pv_kw: np.ndarray
    t_wb_c: np.ndarray
    price_cny_per_kwh: np.ndarray
    cp_flag: np.ndarray

    def slice(self, steps: int) -> "KimLiteInputs":
        return KimLiteInputs(
            timestamps=self.timestamps[:steps],
            q_load_kw_th=self.q_load_kw_th[:steps],
            p_nonplant_kw=self.p_nonplant_kw[:steps],
            p_pv_kw=self.p_pv_kw[:steps],
            t_wb_c=self.t_wb_c[:steps],
            price_cny_per_kwh=self.price_cny_per_kwh[:steps],
            cp_flag=self.cp_flag[:steps],
        )


@dataclass(frozen=True)
class KimLiteSolution:
    status: str
    objective_value: float
    solver_time_s: float
    q_chiller_kw_th: np.ndarray
    q_tes_net_kw_th: np.ndarray
    soc: np.ndarray
    p_plant_kw: np.ndarray
    p_grid_pos_kw: np.ndarray
    p_spill_kw: np.ndarray
    d_peak_kw: float
    mode_index: np.ndarray
    peak_slack_kw: np.ndarray
    mode_integrality: str = "fixed"
    strict_success: bool = True
    fallback_reason: str = ""
    mode_fractionality_max: float = 0.0
    mode_fractionality_mean: float = 0.0
    mode_fractionality_count: int = 0
    mode_fractionality_hours: float = 0.0
    solver_message: str = ""
    plant_tracking_error_kw_th: np.ndarray | None = None


def build_inputs(
    cfg: KimLiteConfig,
    steps: int,
    tariff_gamma: float = 1.0,
    cp_uplift: float = 0.0,
    pv_scale: float | None = None,
) -> KimLiteInputs:
    """Build deterministic 15-minute inputs from project PV/price CSVs."""

    start = datetime.fromisoformat(cfg.start_timestamp.replace("T", " "))
    timestamps = [start + timedelta(minutes=15 * i) for i in range(steps)]
    pv = _take_cyclic(_load_hourly_series(cfg.pv_csv), timestamps) * float(pv_scale or cfg.pv_scale)
    base_price = _take_cyclic(_load_hourly_series(cfg.price_csv), timestamps)
    cp_flag = _critical_peak_flags(timestamps, cfg.critical_peak.months, cfg.critical_peak.windows)
    price, cp_flag = _apply_tou_transform(base_price, cfg.alpha_float, tariff_gamma, cp_uplift, cp_flag)
    hours = np.asarray([t.hour + t.minute / 60.0 for t in timestamps], dtype=float)
    load_shape = 1.0 + cfg.q_load_daily_amp_frac * np.sin(2.0 * np.pi * (hours - 14.0) / 24.0)
    q_load = np.maximum(0.0, cfg.q_load_kw_th * load_shape)
    p_nonplant = np.full(steps, cfg.p_nonplant_kw, dtype=float)
    t_wb = cfg.wet_bulb_base_c + cfg.wet_bulb_amp_c * np.sin(2.0 * np.pi * (hours - 15.0) / 24.0)
    return KimLiteInputs(
        timestamps=timestamps,
        q_load_kw_th=q_load,
        p_nonplant_kw=p_nonplant,
        p_pv_kw=pv,
        t_wb_c=t_wb,
        price_cny_per_kwh=price,
        cp_flag=cp_flag,
    )


def solve_paper_like_mpc(
    cfg: KimLiteConfig,
    inputs: KimLiteInputs,
    tes_enabled: bool = True,
    peak_cap_kw: float | None = None,
    enforce_signed_ramp: bool = False,
    mode_integrality: str = "strict",
    previous_u_signed: float = 0.0,
) -> KimLiteSolution:
    """Solve the Kim-like cold plant + signed-net-TES MILP."""

    n = len(inputs.timestamps)
    m = len(cfg.modes)
    if mode_integrality not in {"strict", "relaxed"}:
        raise ValueError("mode_integrality must be 'strict' or 'relaxed'")
    cfg = _with_reachable_modes(cfg, inputs, tes_enabled)
    m = len(cfg.modes)
    if mode_integrality == "relaxed" and m > 1:
        raise RuntimeError("relaxed mode is only allowed for single-mode proxy tests")
    relax_mode_binaries = mode_integrality == "relaxed"
    idx = _Index(n=n, m=m, peak_cap=peak_cap_kw is not None)
    c = np.zeros(idx.nvar)
    lb = np.zeros(idx.nvar)
    ub = np.full(idx.nvar, np.inf)
    integrality = np.zeros(idx.nvar)

    for j in range(m):
        for k in range(n):
            integrality[idx.s(j, k)] = 0 if relax_mode_binaries else 1
            ub[idx.s(j, k)] = 1.0
            ub[idx.nu(j, k)] = cfg.modes[j].q_max_kw_th
    for k in range(n + 1):
        lb[idx.soc(k)] = cfg.tes.soc_min
        ub[idx.soc(k)] = cfg.tes.soc_max
    for k in range(n):
        c[idx.grid(k)] = inputs.price_cny_per_kwh[k] * cfg.dt_hours
        c[idx.spill(k)] = cfg.objective.w_spill * cfg.dt_hours
        if idx.peak_cap:
            c[idx.cap_slack(k)] = cfg.objective.w_peak_slack * cfg.dt_hours
    c[idx.d_peak()] = cfg.objective.w_peak
    c[idx.term_pos()] = cfg.objective.w_terminal
    c[idx.term_neg()] = cfg.objective.w_terminal

    rows: list[np.ndarray] = []
    lower: list[float] = []
    upper: list[float] = []

    def add(row: np.ndarray, lo: float, hi: float) -> None:
        rows.append(row)
        lower.append(lo)
        upper.append(hi)

    for k in range(n):
        row = np.zeros(idx.nvar)
        for j in range(m):
            row[idx.s(j, k)] = 1.0
        add(row, -np.inf, 1.0)

    for j, mode in enumerate(cfg.modes):
        for k in range(n):
            row = np.zeros(idx.nvar)
            row[idx.nu(j, k)] = 1.0
            row[idx.s(j, k)] = -mode.q_max_kw_th
            add(row, -np.inf, 0.0)
            row = np.zeros(idx.nvar)
            row[idx.nu(j, k)] = -1.0
            row[idx.s(j, k)] = mode.q_min_kw_th
            add(row, -np.inf, 0.0)

    row = np.zeros(idx.nvar)
    row[idx.soc(0)] = 1.0
    add(row, cfg.tes.initial_soc, cfg.tes.initial_soc)

    decay = 1.0 - cfg.tes.loss_per_h * cfg.dt_hours
    if tes_enabled:
        for k in range(n):
            row = np.zeros(idx.nvar)
            row[idx.soc(k + 1)] = 1.0
            row[idx.soc(k)] = -decay
            for j in range(m):
                row[idx.nu(j, k)] = -cfg.dt_hours / cfg.tes.capacity_kwh_th
            rhs = -inputs.q_load_kw_th[k] * cfg.dt_hours / cfg.tes.capacity_kwh_th
            add(row, rhs, rhs)
            row = np.zeros(idx.nvar)
            for j in range(m):
                row[idx.nu(j, k)] = 1.0
            add(row, -np.inf, inputs.q_load_kw_th[k] + cfg.tes.q_ch_max_kw_th)
            row = np.zeros(idx.nvar)
            for j in range(m):
                row[idx.nu(j, k)] = -1.0
            add(row, -np.inf, cfg.tes.q_dis_max_kw_th - inputs.q_load_kw_th[k])
    else:
        for k in range(n):
            row = np.zeros(idx.nvar)
            for j in range(m):
                row[idx.nu(j, k)] = 1.0
            add(row, inputs.q_load_kw_th[k], inputs.q_load_kw_th[k])
        for k in range(1, n + 1):
            row = np.zeros(idx.nvar)
            row[idx.soc(k)] = 1.0
            add(row, cfg.tes.initial_soc, cfg.tes.initial_soc)

    row = np.zeros(idx.nvar)
    row[idx.soc(n)] = 1.0
    row[idx.term_pos()] = -1.0
    row[idx.term_neg()] = 1.0
    add(row, cfg.tes.soc_target, cfg.tes.soc_target)

    for k in range(n):
        plant_terms = _plant_terms(cfg.modes, inputs.t_wb_c[k])
        row = np.zeros(idx.nvar)
        row[idx.grid(k)] = -1.0
        for j, (a, b) in enumerate(plant_terms):
            row[idx.nu(j, k)] = a
            row[idx.s(j, k)] = b
        add(row, -np.inf, inputs.p_pv_kw[k] - inputs.p_nonplant_kw[k])
        row = np.zeros(idx.nvar)
        row[idx.spill(k)] = -1.0
        for j, (a, b) in enumerate(plant_terms):
            row[idx.nu(j, k)] = -a
            row[idx.s(j, k)] = -b
        add(row, -np.inf, inputs.p_nonplant_kw[k] - inputs.p_pv_kw[k])
        row = np.zeros(idx.nvar)
        row[idx.grid(k)] = 1.0
        row[idx.d_peak()] = -1.0
        add(row, -np.inf, 0.0)
        if peak_cap_kw is not None:
            row = np.zeros(idx.nvar)
            row[idx.grid(k)] = 1.0
            row[idx.cap_slack(k)] = -1.0
            add(row, -np.inf, float(peak_cap_kw))

    if enforce_signed_ramp:
        _add_signed_ramp_constraints(rows, lower, upper, idx, cfg, inputs, previous_u_signed)

    start = time.perf_counter()
    result = milp(
        c=c,
        integrality=integrality,
        bounds=Bounds(lb, ub),
        constraints=LinearConstraint(np.asarray(rows), np.asarray(lower), np.asarray(upper)),
        options={"time_limit": cfg.solver_time_limit_s},
    )
    solver_time = time.perf_counter() - start
    if not result.success or result.x is None:
        raise RuntimeError(f"Kim-lite MILP infeasible or failed: {result.message}")
    x = np.asarray(result.x)
    status = "optimal_relaxed_modes" if relax_mode_binaries else "optimal"
    fractionality = _mode_fractionality_stats(idx, x, cfg.dt_hours)
    return _solution_from_x(
        cfg,
        inputs,
        idx,
        x,
        status,
        float(result.fun),
        solver_time,
        mode_integrality=mode_integrality,
        mode_fractionality_stats=fractionality,
        solver_message=str(result.message),
    )


def plant_dispatch(q_chiller_kw_th: float, cfg: KimLiteConfig, t_wb_c: float) -> tuple[float, float, int]:
    """Dispatch a requested chiller output to the smallest feasible mode."""

    if q_chiller_kw_th <= 1e-7:
        return 0.0, 0.0, -1
    modes = sorted(enumerate(cfg.modes), key=lambda item: item[1].q_max_kw_th)
    for idx, mode in modes:
        if q_chiller_kw_th <= mode.q_max_kw_th + 1e-9:
            q = max(q_chiller_kw_th, mode.q_min_kw_th)
            p = mode.a_kw_per_kwth * q + mode.b_kw + mode.c_kw_per_c * t_wb_c
            return q, p, idx
    idx, mode = modes[-1]
    q = mode.q_max_kw_th
    p = mode.a_kw_per_kwth * q + mode.b_kw + mode.c_kw_per_c * t_wb_c
    return q, p, idx


def _with_reachable_modes(cfg: KimLiteConfig, inputs: KimLiteInputs, tes_enabled: bool) -> KimLiteConfig:
    """Remove plant modes that cannot intersect the horizon's feasible chiller-output range."""

    if len(cfg.modes) <= 1:
        return cfg
    if tes_enabled:
        q_lo = np.maximum(0.0, inputs.q_load_kw_th - cfg.tes.q_dis_max_kw_th)
        q_hi = inputs.q_load_kw_th + cfg.tes.q_ch_max_kw_th
    else:
        q_lo = inputs.q_load_kw_th
        q_hi = inputs.q_load_kw_th
    modes = tuple(
        mode
        for mode in cfg.modes
        if bool(np.any((q_hi >= mode.q_min_kw_th - 1e-9) & (q_lo <= mode.q_max_kw_th + 1e-9)))
    )
    if not modes:
        return cfg
    return replace(cfg, modes=modes)


def _solution_from_x(
    cfg: KimLiteConfig,
    inputs: KimLiteInputs,
    idx: "_Index",
    x: np.ndarray,
    status: str,
    objective_value: float,
    solver_time_s: float,
    mode_integrality: str,
    mode_fractionality_stats: dict[str, float],
    solver_message: str,
) -> KimLiteSolution:
    n = idx.n
    q_chiller = np.zeros(n)
    p_plant = np.zeros(n)
    mode_index = np.full(n, -1, dtype=int)
    for k in range(n):
        active = []
        for j in range(idx.m):
            q_chiller[k] += x[idx.nu(j, k)]
            if x[idx.s(j, k)] > 0.5:
                active.append(j)
            a, b = _plant_terms(cfg.modes, inputs.t_wb_c[k])[j]
            p_plant[k] += a * x[idx.nu(j, k)] + b * x[idx.s(j, k)]
        if active:
            mode_index[k] = int(active[0])
        elif q_chiller[k] > 1e-6:
            _, _, inferred = plant_dispatch(float(q_chiller[k]), cfg, float(inputs.t_wb_c[k]))
            mode_index[k] = inferred
    q_net = q_chiller - inputs.q_load_kw_th
    peak_slack = np.zeros(n)
    if idx.peak_cap:
        peak_slack = np.asarray([x[idx.cap_slack(k)] for k in range(n)], dtype=float)
    return KimLiteSolution(
        status=status,
        objective_value=objective_value,
        solver_time_s=solver_time_s,
        q_chiller_kw_th=_clean(q_chiller),
        q_tes_net_kw_th=_clean(q_net),
        soc=np.asarray([x[idx.soc(k)] for k in range(n + 1)], dtype=float),
        p_plant_kw=_clean(p_plant),
        p_grid_pos_kw=_clean(np.asarray([x[idx.grid(k)] for k in range(n)], dtype=float)),
        p_spill_kw=_clean(np.asarray([x[idx.spill(k)] for k in range(n)], dtype=float)),
        d_peak_kw=float(x[idx.d_peak()]),
        mode_index=mode_index,
        peak_slack_kw=_clean(peak_slack),
        mode_integrality=mode_integrality,
        strict_success=mode_integrality == "strict",
        fallback_reason="",
        mode_fractionality_max=float(mode_fractionality_stats["max"]),
        mode_fractionality_mean=float(mode_fractionality_stats["mean"]),
        mode_fractionality_count=int(mode_fractionality_stats["count"]),
        mode_fractionality_hours=float(mode_fractionality_stats["hours"]),
        solver_message=solver_message,
    )


def _mode_fractionality_stats(idx: "_Index", x: np.ndarray, dt_hours: float) -> dict[str, float]:
    if idx.m == 0 or idx.n == 0:
        return {"max": 0.0, "mean": 0.0, "count": 0.0, "hours": 0.0}
    arr = np.asarray([[float(x[idx.s(j, k)]) for j in range(idx.m)] for k in range(idx.n)], dtype=float)
    frac = np.minimum(np.abs(arr), np.abs(arr - 1.0))
    fractional_steps = np.any(frac > 1e-6, axis=1)
    count = int(fractional_steps.sum())
    return {
        "max": float(frac.max()),
        "mean": float(frac.mean()),
        "count": float(count),
        "hours": float(count * dt_hours),
    }


def _add_signed_ramp_constraints(
    rows: list[np.ndarray],
    lower: list[float],
    upper: list[float],
    idx: "_Index",
    cfg: KimLiteConfig,
    inputs: KimLiteInputs,
    previous_u_signed: float,
) -> None:
    q_abs = cfg.tes.q_abs_max_kw_th
    row = np.zeros(idx.nvar)
    for j in range(idx.m):
        row[idx.nu(j, 0)] = 1.0 / q_abs
    rows.append(row)
    lower.append(-np.inf)
    upper.append(cfg.signed_du_max + float(previous_u_signed) + inputs.q_load_kw_th[0] / q_abs)
    rows.append(-row)
    lower.append(-np.inf)
    upper.append(cfg.signed_du_max - float(previous_u_signed) - inputs.q_load_kw_th[0] / q_abs)
    for k in range(1, idx.n):
        row = np.zeros(idx.nvar)
        for j in range(idx.m):
            row[idx.nu(j, k)] = 1.0 / q_abs
            row[idx.nu(j, k - 1)] = -1.0 / q_abs
        rhs = cfg.signed_du_max + (inputs.q_load_kw_th[k] - inputs.q_load_kw_th[k - 1]) / q_abs
        rows.append(row)
        lower.append(-np.inf)
        upper.append(rhs)
        rows.append(-row)
        lower.append(-np.inf)
        upper.append(cfg.signed_du_max - (inputs.q_load_kw_th[k] - inputs.q_load_kw_th[k - 1]) / q_abs)


def _plant_terms(modes: tuple[ModeConfig, ...], t_wb_c: float) -> list[tuple[float, float]]:
    return [(m.a_kw_per_kwth, m.b_kw + m.c_kw_per_c * float(t_wb_c)) for m in modes]


def _load_hourly_series(path: str) -> pd.Series:
    frame = pd.read_csv(path)
    if "timestamp" not in frame.columns:
        raise ValueError(f"{path} must contain timestamp")
    value_col = [c for c in frame.columns if c != "timestamp"][0]
    values = pd.to_numeric(frame[value_col], errors="raise").astype(float)
    if "mwh" in value_col.lower():
        values = values / 1000.0
    series = pd.Series(values.to_numpy(), index=pd.to_datetime(frame["timestamp"]))
    return series.sort_index()


def _take_cyclic(series: pd.Series, timestamps: list[datetime]) -> np.ndarray:
    return _resample_cyclic_to_timestamps(series, timestamps)


def _apply_tou_transform(
    price_all_in: np.ndarray,
    alpha_float: float,
    gamma: float,
    cp_uplift: float,
    cp_flag: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    price_all_in = np.asarray(price_all_in, dtype=float)
    cp_flag = np.asarray(cp_flag, dtype=int)
    p_float_base = float(alpha_float) * price_all_in
    p_nonfloat_const = (1.0 - float(alpha_float)) * float(price_all_in.mean())
    mean_float = float(p_float_base.mean())
    transformed_float = mean_float + float(gamma) * (p_float_base - mean_float)
    transformed_float = transformed_float * (1.0 + float(cp_uplift) * cp_flag)
    return np.maximum(0.0, p_nonfloat_const + transformed_float), cp_flag


def _critical_peak_flags(
    timestamps: list[datetime],
    months: tuple[int, ...],
    windows: tuple[tuple[float, float], ...],
) -> np.ndarray:
    month_set = set(months)
    flags: list[int] = []
    for ts in timestamps:
        hour = ts.hour + ts.minute / 60.0
        active = ts.month in month_set and any(start <= hour < end for start, end in windows)
        flags.append(1 if active else 0)
    return np.asarray(flags, dtype=int)


def _resample_cyclic_to_timestamps(series: pd.Series, timestamps: list[datetime]) -> np.ndarray:
    if len(series) == 0:
        raise ValueError("series must not be empty")
    cleaned = pd.Series(pd.to_numeric(series, errors="raise").astype(float).to_numpy(), index=_reference_index(series.index))
    cleaned = cleaned.sort_index()
    cleaned = cleaned[~cleaned.index.duplicated(keep="last")]
    resampled = cleaned.resample("15min").ffill()
    target_index = _reference_index(pd.DatetimeIndex(timestamps))
    values = resampled.reindex(target_index, method="ffill")
    if values.isna().any():
        values = values.fillna(float(resampled.iloc[-1]))
    return values.to_numpy(dtype=float)


def _reference_index(index: pd.Index) -> pd.DatetimeIndex:
    return pd.DatetimeIndex([pd.Timestamp(ts).replace(year=2000) for ts in index])


def _clean(values: np.ndarray) -> np.ndarray:
    out = np.asarray(values, dtype=float)
    out[np.abs(out) < 1e-7] = 0.0
    return out


@dataclass(frozen=True)
class _Index:
    n: int
    m: int
    peak_cap: bool = False

    @property
    def base_nu(self) -> int:
        return self.m * self.n

    @property
    def base_soc(self) -> int:
        return 2 * self.m * self.n

    @property
    def base_grid(self) -> int:
        return self.base_soc + self.n + 1

    @property
    def base_spill(self) -> int:
        return self.base_grid + self.n

    @property
    def base_tail(self) -> int:
        return self.base_spill + self.n + 1

    @property
    def nvar(self) -> int:
        return self.base_tail + 2 + (self.n if self.peak_cap else 0)

    def s(self, j: int, k: int) -> int:
        return j * self.n + k

    def nu(self, j: int, k: int) -> int:
        return self.base_nu + j * self.n + k

    def soc(self, k: int) -> int:
        return self.base_soc + k

    def grid(self, k: int) -> int:
        return self.base_grid + k

    def spill(self, k: int) -> int:
        return self.base_spill + k

    def d_peak(self) -> int:
        return self.base_spill + self.n

    def term_pos(self) -> int:
        return self.base_tail

    def term_neg(self) -> int:
        return self.base_tail + 1

    def cap_slack(self, k: int) -> int:
        if not self.peak_cap:
            raise IndexError("peak cap slack is not enabled")
        return self.base_tail + 2 + k
