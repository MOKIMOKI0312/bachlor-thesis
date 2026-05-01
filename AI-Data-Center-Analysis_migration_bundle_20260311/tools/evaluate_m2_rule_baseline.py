"""Rule-based M2 TES baseline.

This script runs the full M2 evaluation environment with a deterministic
hand-written TES policy.  It is intentionally separate from RL training:
the goal is to verify whether the physical TES loop can charge/discharge
under a clear TOU control rule before spending more time on agent tuning.

Sign convention follows TESTargetValveWrapper:
    valve > 0: discharge/use TES
    valve < 0: charge/source TES

The rule policy returns the exposed 4D M2-F1 action:
    [CT_Pump_DRL, CRAH_T_DRL, Chiller_T_DRL, TES_DRL]
CRAH_Fan_DRL remains a fixed full-env action at index 0.

Example:
    python tools/evaluate_m2_rule_baseline.py --tag m2f1_rule_tou
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

import gymnasium as gym
import numpy as np
import pandas as pd

from sinergym.envs.energy_scale_wrapper import EnergyScaleWrapper
from sinergym.envs.price_signal_wrapper import PriceSignalWrapper
from sinergym.envs.pv_signal_wrapper import PVSignalWrapper
from sinergym.envs.temp_trend_wrapper import TempTrendWrapper
from sinergym.envs.tes_wrapper import FixedActionInsertWrapper, TESTargetValveWrapper
from sinergym.envs.time_encoding_wrapper import TimeEncodingWrapper
from sinergym.utils.common import get_ids
from sinergym.utils.wrappers import LoggerWrapper
from tools.m2_action_guard import M2_FIXED_FAN_VALUE


DEFAULT_EPW = "CHN_JS_Nanjing.582380_TMYx.2009-2023.epw"
DEFAULT_PRICE_CSV = "Data/prices/Jiangsu_TOU_2025_hourly.csv"
DEFAULT_PV_CSV = "Data/pv/CHN_Nanjing_PV_6MWp_hourly.csv"

TES_TANK_M3 = 1400.0
TES_MAX_FLOW_KG_S = 389.0
M2_TIMESTEPS_PER_HOUR = 4


def build_env(args: argparse.Namespace) -> gym.Env:
    env = gym.make(
        "Eplus-DC-Cooling-TES",
        env_name=f"rule-m2-{args.tag}-{args.policy}",
        building_file="DRL_DC_evaluation.epJSON",
        weather_files=args.epw,
        config_params={
            "runperiod": (1, 1, 2025, 31, 12, 2025),
            "timesteps_per_hour": M2_TIMESTEPS_PER_HOUR,
        },
        evaluation_flag=1,
    )
    env = TESTargetValveWrapper(
        env,
        valve_idx=4,
        rate_limit=args.tes_valve_rate_limit,
        soc_low_guard=args.tes_guard_soc_low,
        soc_high_guard=args.tes_guard_soc_high,
    )
    env = FixedActionInsertWrapper(
        env,
        fixed_actions={0: args.fan_action},
        fixed_action_names={0: "CRAH_Fan_DRL"},
    )
    env = TimeEncodingWrapper(env)
    env = TempTrendWrapper(
        env,
        epw_path=Path("Data/weather") / (args.epw if isinstance(args.epw, str) else args.epw[0]),
        lookahead_hours=6,
    )
    env = PriceSignalWrapper(env, price_csv_path=args.price_csv)
    env = PVSignalWrapper(env, pv_csv_path=args.pv_csv, dc_peak_load_kw=args.dc_peak_load_kw)
    env = EnergyScaleWrapper(env, energy_indices=[13, 14], scale=1.0 / 3.6e9)
    return env


def attach_reward(env: gym.Env, args: argparse.Namespace) -> gym.Env:
    """Patch the same RL cost reward used by M2 evaluation for diagnostics."""
    if args.reward_cls == "pue_tes":
        return env

    from sinergym.utils.rewards import RL_Cost_Reward, RL_Green_Reward

    price = pd.read_csv(args.price_csv)["price_usd_per_mwh"].to_numpy(dtype=np.float32)
    pv = pd.read_csv(args.pv_csv)["power_kw"].to_numpy(dtype=np.float32)
    kwargs = dict(
        temperature_variables=["air_temperature"],
        energy_variables=["Electricity:Facility"],
        ITE_variables=["ITE-CPU:InteriorEquipment:Electricity"],
        range_comfort_winter=(18.0, 25.0),
        range_comfort_summer=(18.0, 25.0),
        energy_weight=0.5,
        lambda_energy=1.0,
        lambda_temperature=1.0,
        soc_variable="TES_SOC",
        soc_low=0.15,
        soc_high=0.85,
        soc_warn_low=0.15,
        soc_warn_high=0.85,
        lambda_soc=2.0,
        lambda_soc_warn=1.0,
        price_series=price,
        alpha=args.alpha,
        beta=args.beta,
        kappa_shape=args.kappa_shape,
        gamma_pbrs=args.gamma_pbrs,
        tau_decay=args.tau_decay,
        p_peak_ref=args.p_peak_ref,
    )
    if args.reward_cls == "rl_cost":
        cls = RL_Cost_Reward
    else:
        cls = RL_Green_Reward
        kwargs["pv_series"] = pv
        kwargs["c_pv"] = args.c_pv
        kwargs["pv_threshold_kw"] = args.pv_threshold_kw

    eplus_env = env.unwrapped
    if not hasattr(eplus_env, "reward_fn"):
        raise RuntimeError(f"env.unwrapped={type(eplus_env).__name__} has no reward_fn")
    eplus_env.reward_fn = cls(**kwargs)
    if not isinstance(eplus_env.reward_fn, cls):
        raise RuntimeError(f"reward patch failed, got {type(eplus_env.reward_fn).__name__}")
    return env


def _idx(names: list[str], name: str) -> int:
    if name not in names:
        raise RuntimeError(f"{name!r} not found in observation_variables: {names}")
    return names.index(name)


def policy_action(obs: np.ndarray, names: list[str], args: argparse.Namespace) -> np.ndarray:
    soc = float(obs[_idx(names, "TES_SOC")])
    price = float(obs[_idx(names, "price_current_norm")])
    hours_to_peak = float(obs[_idx(names, "price_hours_to_next_peak_norm")])

    tes_target = 0.0
    if args.policy == "neutral":
        tes_target = 0.0
    elif args.policy == "charge":
        if soc < args.soc_charge_limit:
            tes_target = -args.charge_target
    elif args.policy == "discharge":
        if soc > args.soc_discharge_limit:
            tes_target = args.discharge_target
    elif args.policy == "tou":
        if price >= args.high_price_threshold and soc > args.soc_discharge_limit:
            tes_target = args.discharge_target
        elif (
            price <= args.low_price_threshold
            and hours_to_peak <= args.near_peak_threshold
            and soc < args.soc_charge_limit
        ):
            tes_target = -args.charge_target
    else:
        raise RuntimeError(f"Unsupported policy={args.policy!r}")

    return np.array(
        [
            args.ct_pump_action,
            args.crah_temp_action,
            args.chiller_temp_action,
            tes_target,
        ],
        dtype=np.float32,
    )


def _energy_mwh(series: pd.Series) -> tuple[np.ndarray, str]:
    values = series.astype(float)
    if float(values.abs().median()) > 1.0e5:
        return (values / 3.6e9).to_numpy(), "J"
    return values.to_numpy(), "MWh"


def summarize_monitor(
    df: pd.DataFrame,
    args: argparse.Namespace,
    steps: int,
    total_reward: float,
    elapsed: float,
    monitor_path: Path,
) -> dict:
    if not df.columns.is_unique:
        duplicated = df.columns[df.columns.duplicated()].tolist()
        raise RuntimeError(f"Duplicate monitor columns in {monitor_path}: {duplicated}")

    facility_MWh_step, energy_unit = _energy_mwh(df["Electricity:Facility"])
    ite_MWh_step, _ = _energy_mwh(df["ITE-CPU:InteriorEquipment:Electricity"])
    temps = df["air_temperature"].astype(float)
    valves = df["TES_valve_wrapper_position"].astype(float)
    soc = df["TES_SOC"].astype(float)

    total_facility_MWh = float(facility_MWh_step.sum())
    total_ite_MWh = float(ite_MWh_step.sum())
    pue = total_facility_MWh / total_ite_MWh if total_ite_MWh > 0 else float("nan")
    comfort_pct = float((temps > 25.0).sum() / max(len(temps), 1) * 100.0)

    price = pd.read_csv(args.price_csv)["price_usd_per_mwh"].to_numpy(dtype=np.float64)
    pv = pd.read_csv(args.pv_csv)["power_kw"].to_numpy(dtype=np.float64)
    hour_idx = (np.arange(len(facility_MWh_step)) // M2_TIMESTEPS_PER_HOUR) % len(price)
    lmp_step = price[hour_idx]
    pv_step = pv[hour_idx]
    cost_usd = float((facility_MWh_step * lmp_step).sum())

    dt_hours = 1.0 / M2_TIMESTEPS_PER_HOUR
    facility_kW_step = facility_MWh_step / dt_hours * 1000.0
    self_cons_kWh = np.minimum(facility_kW_step, pv_step).sum() * dt_hours
    facility_kWh = total_facility_MWh * 1000.0
    pv_self_consumption_pct = float(
        self_cons_kWh / facility_kWh * 100.0 if facility_kWh > 0 else 0.0
    )

    price_signal = df["price_current_norm"].astype(float)
    low_price_valves = valves[price_signal <= price_signal.quantile(0.25)]
    high_price_valves = valves[price_signal >= price_signal.quantile(0.75)]
    price_low_valve_mean = float(low_price_valves.mean()) if len(low_price_valves) else None
    price_high_valve_mean = float(high_price_valves.mean()) if len(high_price_valves) else None
    price_response = (
        price_high_valve_mean - price_low_valve_mean
        if price_high_valve_mean is not None and price_low_valve_mean is not None
        else None
    )

    pv_signal = df["pv_current_ratio"].astype(float)
    low_pv_valves = valves[pv_signal <= pv_signal.quantile(0.25)]
    high_pv_valves = valves[pv_signal >= pv_signal.quantile(0.75)]
    pv_low_valve_mean = float(low_pv_valves.mean()) if len(low_pv_valves) else None
    pv_high_valve_mean = float(high_pv_valves.mean()) if len(high_pv_valves) else None
    pv_response = (
        pv_high_valve_mean - pv_low_valve_mean
        if pv_high_valve_mean is not None and pv_low_valve_mean is not None
        else None
    )

    valves_effective = np.where(valves.abs().to_numpy() > 0.01, valves.abs().to_numpy(), 0.0)
    cycles_rough = float(
        valves_effective.sum()
        * TES_MAX_FLOW_KG_S
        * (3600.0 / M2_TIMESTEPS_PER_HOUR)
        / 1000.0
        / TES_TANK_M3
    )

    soc_np = soc.to_numpy()
    steps_per_day = 24 * M2_TIMESTEPS_PER_HOUR
    n_days = len(soc_np) // steps_per_day
    daily_amp = np.array(
        [
            soc_np[d * steps_per_day:(d + 1) * steps_per_day].max()
            - soc_np[d * steps_per_day:(d + 1) * steps_per_day].min()
            for d in range(n_days)
        ],
        dtype=np.float64,
    )
    soc_daily_amplitude_mean = float(daily_amp.mean()) if len(daily_amp) else 0.0
    tes_activated = bool(cycles_rough >= 100.0 and soc_daily_amplitude_mean >= 0.3)

    return {
        "tag": args.tag,
        "policy": args.policy,
        "reward_cls": args.reward_cls,
        "steps": steps,
        "max_steps": args.max_steps,
        "total_reward": total_reward,
        "total_facility_MWh": total_facility_MWh,
        "total_ite_MWh": total_ite_MWh,
        "energy_unit_detected": energy_unit,
        "pue": pue,
        "comfort_violation_pct": comfort_pct,
        "mean_temperature_C": float(temps.mean()),
        "max_temperature_C": float(temps.max()),
        "p95_temperature_C": float(temps.quantile(0.95)),
        "cost_usd": cost_usd,
        "pv_self_consumption_pct": pv_self_consumption_pct,
        "tes_annual_cycles_rough": cycles_rough,
        "tes_soc_daily_amplitude_mean": soc_daily_amplitude_mean,
        "tes_activated": tes_activated,
        "valve_mean_abs": float(valves.abs().mean()),
        "valve_active_fraction": float((valves.abs() > 0.05).mean()),
        "valve_saturation_fraction": float((valves.abs() > 0.95).mean()),
        "charge_fraction": float((valves < -0.05).mean()),
        "discharge_fraction": float((valves > 0.05).mean()),
        "soc_min": float(soc.min()),
        "soc_mean": float(soc.mean()),
        "soc_max": float(soc.max()),
        "price_low_valve_mean": price_low_valve_mean,
        "price_high_valve_mean": price_high_valve_mean,
        "price_response_high_minus_low": price_response,
        "pv_low_valve_mean": pv_low_valve_mean,
        "pv_high_valve_mean": pv_high_valve_mean,
        "pv_response_high_minus_low": pv_response,
        "monitor_csv": str(monitor_path),
        "elapsed_seconds": elapsed,
        "rule": {
            "high_price_threshold": args.high_price_threshold,
            "low_price_threshold": args.low_price_threshold,
            "near_peak_threshold": args.near_peak_threshold,
            "soc_charge_limit": args.soc_charge_limit,
            "soc_discharge_limit": args.soc_discharge_limit,
            "charge_target": -args.charge_target,
            "discharge_target": args.discharge_target,
            "fixed_fan_action": args.fan_action,
            "fixed_non_tes_agent_action": [
                args.ct_pump_action,
                args.crah_temp_action,
                args.chiller_temp_action,
            ],
        },
    }


def write_summary(result: dict, out_md: Path) -> None:
    lines = [
        f"# M2 Rule Baseline - {result['tag']}",
        "",
        f"- Policy: `{result['policy']}`",
        f"- Steps: {result['steps']}",
        f"- PUE: {result['pue']:.4f}",
        f"- Comfort violation: {result['comfort_violation_pct']:.3f}%",
        f"- Facility energy: {result['total_facility_MWh']:.3f} MWh",
        f"- Cost: {result['cost_usd']:.2f} USD",
        f"- SOC daily amplitude mean: {result['tes_soc_daily_amplitude_mean']:.4f}",
        f"- TES rough annual cycles: {result['tes_annual_cycles_rough']:.2f}",
        f"- TES activated criterion: {result['tes_activated']}",
        f"- Valve active / saturated: {result['valve_active_fraction']:.3f} / {result['valve_saturation_fraction']:.3f}",
        f"- Charge / discharge fraction: {result['charge_fraction']:.3f} / {result['discharge_fraction']:.3f}",
        f"- Price response high-low: {result['price_response_high_minus_low']}",
        f"- SOC min / mean / max: {result['soc_min']:.4f} / {result['soc_mean']:.4f} / {result['soc_max']:.4f}",
        f"- Monitor CSV: `{result['monitor_csv']}`",
    ]
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")


def evaluate(args: argparse.Namespace) -> dict:
    if "Eplus-DC-Cooling-TES" not in get_ids():
        raise RuntimeError("Eplus-DC-Cooling-TES environment is not registered.")

    env = build_env(args)
    env = attach_reward(env, args)
    if env.action_space.shape != (4,):
        raise RuntimeError(f"Expected M2-F1 4D action space, got {env.action_space.shape}")
    obs_vars = list(env.get_wrapper_attr("observation_variables"))
    act_vars = list(env.get_wrapper_attr("action_variables"))
    env = LoggerWrapper(
        env,
        monitor_header=["timestep"] + obs_vars + act_vars
        + [
            "time (hours)",
            "reward",
            "energy_term",
            "ITE_term",
            "comfort_term",
            "cost_term",
            "cost_usd_step",
            "mwh_step",
            "lmp_usd_per_mwh",
            "current_price_usd_per_mwh",
            "current_pv_kw",
            "fixed_CRAH_Fan_DRL",
            "tes_valve_target",
            "tes_valve_position",
            "tes_guard_clipped",
            "tes_action_mode",
            "terminated",
            "truncated",
        ],
    )

    workspace = Path(env.get_wrapper_attr("workspace_path"))
    obs_names = list(env.get_wrapper_attr("observation_variables"))
    started = time.perf_counter()
    obs, _ = env.reset()
    total_reward = 0.0
    steps = 0
    terminated = truncated = False
    try:
        while not (terminated or truncated):
            action = policy_action(obs, obs_names, args)
            if action.shape != (4,):
                raise RuntimeError(f"Rule policy emitted {action.shape}, expected (4,)")
            obs, reward, terminated, truncated, _ = env.step(action)
            total_reward += float(reward)
            steps += 1
            if args.max_steps and steps >= args.max_steps:
                break
    finally:
        env.close()

    monitor_path = workspace / "episode-001" / "monitor.csv"
    if not monitor_path.exists():
        raise RuntimeError(f"Monitor CSV not found: {monitor_path}")
    df = pd.read_csv(monitor_path, index_col=False)
    return summarize_monitor(
        df=df,
        args=args,
        steps=steps,
        total_reward=total_reward,
        elapsed=time.perf_counter() - started,
        monitor_path=monitor_path,
    )


def main() -> None:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default=f"m2_rule_baseline_{stamp}")
    ap.add_argument("--policy", default="tou", choices=["tou", "neutral", "charge", "discharge"])
    ap.add_argument("--reward-cls", default="rl_cost", choices=["pue_tes", "rl_cost", "rl_green"])
    ap.add_argument("--epw", default=DEFAULT_EPW)
    ap.add_argument("--price-csv", default=DEFAULT_PRICE_CSV)
    ap.add_argument("--pv-csv", default=DEFAULT_PV_CSV)
    ap.add_argument("--dc-peak-load-kw", type=float, default=6000.0)
    ap.add_argument("--max-steps", type=int, default=0, help="Optional early stop for smoke runs.")
    ap.add_argument("--alpha", type=float, default=2e-3)
    ap.add_argument("--beta", type=float, default=1.0)
    ap.add_argument("--c-pv", type=float, default=0.0)
    ap.add_argument("--pv-threshold-kw", type=float, default=100.0)
    ap.add_argument("--kappa-shape", type=float, default=0.8)
    ap.add_argument("--gamma-pbrs", type=float, default=0.99)
    ap.add_argument("--tau-decay", type=float, default=4.0)
    ap.add_argument("--p-peak-ref", type=float, default=0.80)
    ap.add_argument("--tes-valve-rate-limit", type=float, default=0.25)
    ap.add_argument("--tes-guard-soc-low", type=float, default=0.10)
    ap.add_argument("--tes-guard-soc-high", type=float, default=0.90)
    ap.add_argument("--high-price-threshold", type=float, default=0.75)
    ap.add_argument("--low-price-threshold", type=float, default=-0.50)
    ap.add_argument("--near-peak-threshold", type=float, default=0.40)
    ap.add_argument("--soc-charge-limit", type=float, default=0.85)
    ap.add_argument("--soc-discharge-limit", type=float, default=0.25)
    ap.add_argument("--charge-target", type=float, default=0.85)
    ap.add_argument("--discharge-target", type=float, default=0.85)
    ap.add_argument("--fan-action", type=float, default=M2_FIXED_FAN_VALUE, help="Fixed full-env CRAH_Fan_DRL value, not an exposed policy action.")
    ap.add_argument("--ct-pump-action", type=float, default=0.5)
    ap.add_argument("--crah-temp-action", type=float, default=0.5)
    ap.add_argument("--chiller-temp-action", type=float, default=0.5)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()
    if abs(args.fan_action - M2_FIXED_FAN_VALUE) > 1e-9:
        print(
            f"[evaluate_m2_rule_baseline] --fan-action is legacy-only under M2-F1; "
            f"forcing fixed CRAH_Fan_DRL={M2_FIXED_FAN_VALUE} instead of {args.fan_action}."
        )
        args.fan_action = M2_FIXED_FAN_VALUE

    result = evaluate(args)
    out = args.out or Path("runs/eval_m2") / f"{args.tag}_{args.policy}" / "result.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    write_summary(result, out.with_suffix(".md"))
    print(json.dumps(result, indent=2))
    print(f"Wrote {out}")
    print(f"Wrote {out.with_suffix('.md')}")


if __name__ == "__main__":
    main()
