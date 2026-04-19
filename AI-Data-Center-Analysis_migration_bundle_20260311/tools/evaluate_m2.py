"""M2 evaluation on CAISO SiliconValley + full wrapper stack.

Loads a single seed's checkpoint + training normalization stats (41-dim M2
env), runs a deterministic year-long evaluation, outputs:
    - PUE / comfort pct / facility MWh / ITE MWh (standard)
    - cost_usd_annual (LMP × P_facility integrated)
    - pv_self_consumption_pct (min(P_facility, pv_kw) / P_facility)
    - TES activation metrics: annual_cycles / soc_daily_amplitude

TES activation criterion (handoff §4.1 / tech route D5):
    annual_cycles ≥ 100 AND soc_daily_amplitude_mean ≥ 0.3

Usage:
    python tools/evaluate_m2.py --seed 7 \
        --checkpoint runs/train/run-XXX/checkpoints/e3_rl_cost_seed7_NNNNNNN_steps.zip \
        --workspace runs/train/run-XXX \
        --reward-cls rl_cost \
        --tag seed7
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

import gymnasium as gym
import numpy as np
import pandas as pd

from sinergym.utils.common import get_ids
from sinergym.utils.wrappers import LoggerWrapper, NormalizeObservation
from sinergym.envs.tes_wrapper import TESIncrementalWrapper
from sinergym.envs.time_encoding_wrapper import TimeEncodingWrapper
from sinergym.envs.price_signal_wrapper import PriceSignalWrapper
from sinergym.envs.pv_signal_wrapper import PVSignalWrapper
from sinergym.envs.workload_wrapper import WorkloadWrapper
from tools.dsac_t import DSAC_T

DEFAULT_EPW = "USA_CA_San.Francisco.Intl.AP.724940_TMYx.2009-2023.epw"
DEFAULT_PRICE_CSV = "Data/prices/CAISO_NP15_2023_hourly.csv"
DEFAULT_PV_CSV = "Data/pv/CAISO_PaloAlto_PV_6MWp_hourly.csv"
DEFAULT_IT_TRACE = "Data/AI Trace Data/Earth_hourly.csv"

# TES sizing (from 建筑模型说明.md) — used for annual cycle estimate
TES_TANK_M3 = 1400.0
TES_MAX_FLOW_KG_S = 97.2  # 1400 m³ / 4 h


def build_env(args) -> gym.Env:
    env = gym.make(
        "Eplus-DC-Cooling-TES",
        env_name=f"eval-m2-{args.tag}",
        building_file="DRL_DC_evaluation.epJSON",
        weather_files=args.epw,
        config_params={"runperiod": (1, 1, 2025, 31, 12, 2025), "timesteps_per_hour": 1},
        evaluation_flag=1,
    )
    env = TESIncrementalWrapper(env, valve_idx=5, delta_max=0.20)
    env = TimeEncodingWrapper(env)
    env = PriceSignalWrapper(env, price_csv_path=args.price_csv)
    env = PVSignalWrapper(env, pv_csv_path=args.pv_csv, dc_peak_load_kw=args.dc_peak_load_kw)
    env = WorkloadWrapper(env, it_trace_csv=args.it_trace, workload_idx=4,
                          flexible_fraction=args.flexible_fraction)
    return env


def attach_reward(env: gym.Env, args) -> gym.Env:
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
        energy_weight=0.5, lambda_energy=1.0, lambda_temperature=3.0,
        soc_variable="TES_SOC",
        soc_low=0.15, soc_high=0.85,
        soc_warn_low=0.30, soc_warn_high=0.70,
        lambda_soc=5.0, lambda_soc_warn=3.0,
        price_series=price, alpha=args.alpha, beta=args.beta,
    )
    if args.reward_cls == "rl_cost":
        cls = RL_Cost_Reward
    else:
        cls = RL_Green_Reward
        kwargs["pv_series"] = pv
        kwargs["c_pv"] = args.c_pv
        kwargs["pv_threshold_kw"] = args.pv_threshold_kw

    inner = env
    while hasattr(inner, "env") and not hasattr(inner, "reward_fn"):
        inner = inner.env
    inner.reward_fn = cls(**kwargs)
    return env


def evaluate(args) -> dict:
    if "Eplus-DC-Cooling-TES" not in get_ids():
        raise RuntimeError("Eplus-DC-Cooling-TES environment is not registered.")

    mean = np.loadtxt(args.workspace / "mean.txt", dtype="float")
    var = np.loadtxt(args.workspace / "var.txt", dtype="float")
    if mean.shape[0] != 41 or var.shape[0] != 41:
        raise RuntimeError(
            f"Expected 41-dim M2 normalization stats, got mean={mean.shape}, var={var.shape}. "
            f"Confirm --workspace points to an M2 training run."
        )

    env = build_env(args)
    env = attach_reward(env, args)
    env = NormalizeObservation(env, mean=mean, var=var, automatic_update=False)
    obs_vars = env.get_wrapper_attr("observation_variables")
    act_vars = env.get_wrapper_attr("action_variables")
    env = LoggerWrapper(
        env,
        monitor_header=["timestep"] + list(obs_vars) + list(act_vars)
        + ["time (hours)", "reward", "energy_term", "ITE_term", "comfort_term", "cost_term",
           "terminated", "truncated"],
    )

    model = DSAC_T.load(str(args.checkpoint), device="cpu")
    workspace_post = Path(env.get_wrapper_attr("workspace_path"))

    started = time.perf_counter()
    obs, _ = env.reset()
    term = trunc = False
    step = 0
    total_reward = 0.0
    while not (term or trunc):
        action, _ = model.predict(obs, deterministic=True)
        obs, reward, term, trunc, _ = env.step(action)
        total_reward += float(reward)
        step += 1

    env.close()

    # Parse monitor.csv with pandas (avoids csv.DictReader duplicate-header issue)
    monitor_path = workspace_post / "episode-001" / "monitor.csv"
    df = pd.read_csv(monitor_path)

    facility_J = df["Electricity:Facility"].astype(float)
    ite_J = df["ITE-CPU:InteriorEquipment:Electricity"].astype(float)
    temps = df["air_temperature"].astype(float)
    valves = df["TES_valve_wrapper_position"].astype(float)
    soc = df["TES_SOC"].astype(float)

    total_facility_MWh = float(facility_J.sum() / 3.6e9)
    total_ite_MWh = float(ite_J.sum() / 3.6e9)
    pue = total_facility_MWh / total_ite_MWh if total_ite_MWh > 0 else float("nan")
    comfort_pct = float((temps > 25.0).sum() / max(len(temps), 1) * 100)

    # Cost (USD): facility_MWh * LMP (aligned by hour; CSV has 8760 hourly rows)
    lmp = pd.read_csv(args.price_csv)["price_usd_per_mwh"].to_numpy()
    facility_MWh_hourly = (facility_J / 3.6e9).to_numpy()
    n = min(len(lmp), len(facility_MWh_hourly))
    cost_usd_annual = float((facility_MWh_hourly[:n] * lmp[:n]).sum())

    # PV self-consumption
    pv = pd.read_csv(args.pv_csv)["power_kw"].to_numpy()
    facility_kW_hourly = facility_MWh_hourly * 1000.0  # MWh/h = MW → kW
    self_cons = np.minimum(facility_kW_hourly[:n], pv[:n]).sum()
    pv_self_consumption_pct = float(self_cons / facility_kW_hourly[:n].sum() * 100
                                     if facility_kW_hourly[:n].sum() > 0 else 0)

    # TES activation: annual cycles + SOC daily amplitude
    # 1 cycle = |valve_fraction| × TES_MAX_FLOW integrated over 1 hour / tank_volume
    # Rough proxy: total_charge_volume_kg / rho_water ≈ cumulative valve hours × 97.2 kg/s × 3600
    valve_abs_mean = float(valves.abs().mean())
    # Each timestep is 1h = 3600 s at 97.2 kg/s max. |valve| fraction of that:
    cycles_rough = float(valves.abs().sum() * TES_MAX_FLOW_KG_S * 3600 / 1000 / TES_TANK_M3)
    # SOC daily amplitude: mean of (daily max - daily min)
    soc_np = soc.to_numpy()
    n_days = len(soc_np) // 24
    daily_amp = np.array([soc_np[d*24:(d+1)*24].max() - soc_np[d*24:(d+1)*24].min()
                          for d in range(n_days)])
    soc_daily_amplitude_mean = float(daily_amp.mean()) if len(daily_amp) else 0.0

    tes_activated = bool(cycles_rough >= 100 and soc_daily_amplitude_mean >= 0.3)

    return {
        "seed": args.tag,
        "reward_cls": args.reward_cls,
        "checkpoint": str(args.checkpoint),
        "steps": step,
        "total_reward": total_reward,
        "total_facility_MWh": total_facility_MWh,
        "total_ite_MWh": total_ite_MWh,
        "pue": pue,
        "comfort_violation_pct": comfort_pct,
        "mean_temperature_C": float(temps.mean()),
        "max_temperature_C": float(temps.max()),
        "p95_temperature_C": float(temps.quantile(0.95)),
        "cost_usd_annual": cost_usd_annual,
        "pv_self_consumption_pct": pv_self_consumption_pct,
        "tes_annual_cycles_rough": cycles_rough,
        "tes_soc_daily_amplitude_mean": soc_daily_amplitude_mean,
        "tes_activated": tes_activated,
        "valve_mean_abs": valve_abs_mean,
        "monitor_csv": str(monitor_path),
        "elapsed_seconds": time.perf_counter() - started,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True, help="seedN tag for naming")
    ap.add_argument("--checkpoint", type=Path, required=True)
    ap.add_argument("--workspace", type=Path, required=True)
    ap.add_argument("--reward-cls", default="rl_cost", choices=["pue_tes", "rl_cost", "rl_green"])
    ap.add_argument("--epw", default=DEFAULT_EPW)
    ap.add_argument("--price-csv", default=DEFAULT_PRICE_CSV)
    ap.add_argument("--pv-csv", default=DEFAULT_PV_CSV)
    ap.add_argument("--it-trace", default=DEFAULT_IT_TRACE)
    ap.add_argument("--dc-peak-load-kw", type=float, default=6000.0)
    ap.add_argument("--flexible-fraction", type=float, default=0.3)
    ap.add_argument("--alpha", type=float, default=1e-3)
    ap.add_argument("--beta", type=float, default=1.0)
    ap.add_argument("--c-pv", type=float, default=0.0)
    ap.add_argument("--pv-threshold-kw", type=float, default=100.0)
    ap.add_argument("--out", type=Path, default=None, help="Output JSON path (default: runs/eval_m2/<tag>/result.json)")
    args = ap.parse_args()

    result = evaluate(args)
    print(json.dumps(result, indent=2))

    out = args.out or Path("runs/eval_m2") / args.tag / "result.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
