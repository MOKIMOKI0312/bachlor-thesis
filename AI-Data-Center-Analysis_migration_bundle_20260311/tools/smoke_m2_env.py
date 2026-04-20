"""Integration smoke for the full M2 wrapper stack on a real EplusEnv.

Builds:  EplusEnv → TESIncremental → TimeEncoding → TempTrend → PriceSignal →
         PVSignal → WorkloadWrapper → (+ RL_Cost_Reward patched)

Verifies:
  - obs_dim == 41 (20 + 6 + 3 + 3 + 9) — post-H2a/H2b/H2c/H2d, tech route §6.1
  - action_dim == 6
  - 3 env.step calls run clean
  - reward_terms dict contains cost_term / lmp_usd_per_mwh (RL-Cost)
    or effective_price_usd_per_mwh (RL-Green)

Run:
  EPLUS_PATH=... PYTHONPATH="$PWD;$EPLUS_PATH" python tools/smoke_m2_env.py --reward-cls rl_cost
  EPLUS_PATH=... PYTHONPATH="$PWD;$EPLUS_PATH" python tools/smoke_m2_env.py --reward-cls rl_green
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import gymnasium as gym
import numpy as np

from sinergym.utils.common import get_ids
from sinergym.envs.tes_wrapper import TESIncrementalWrapper
from sinergym.envs.time_encoding_wrapper import TimeEncodingWrapper
from sinergym.envs.temp_trend_wrapper import TempTrendWrapper
from sinergym.envs.price_signal_wrapper import PriceSignalWrapper
from sinergym.envs.pv_signal_wrapper import PVSignalWrapper
from sinergym.envs.workload_wrapper import WorkloadWrapper


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reward-cls", default="rl_cost", choices=["pue_tes", "rl_cost", "rl_green"])
    ap.add_argument("--steps", type=int, default=3)
    args = ap.parse_args()

    assert "Eplus-DC-Cooling-TES" in get_ids()

    stamp = datetime.today().strftime("%Y-%m-%d_%H-%M-%S")
    env = gym.make(
        "Eplus-DC-Cooling-TES",
        env_name=f"{stamp}_smoke_m2_{args.reward_cls}",
        building_file=["DRL_DC_training.epJSON"],
        weather_files=["USA_CA_San.Francisco.Intl.AP.724940_TMYx.2009-2023.epw"],
        config_params={"runperiod": (1, 1, 2025, 31, 12, 2025), "timesteps_per_hour": 1},
    )
    env = TESIncrementalWrapper(env, valve_idx=5, delta_max=0.20)
    env = TimeEncodingWrapper(env)
    env = TempTrendWrapper(
        env,
        epw_path="Data/weather/USA_CA_San.Francisco.Intl.AP.724940_TMYx.2009-2023.epw",
        lookahead_hours=6,
    )
    env = PriceSignalWrapper(env, price_csv_path="Data/prices/CAISO_NP15_2023_hourly.csv")
    env = PVSignalWrapper(env, pv_csv_path="Data/pv/CAISO_PaloAlto_PV_6MWp_hourly.csv")
    env = WorkloadWrapper(env, it_trace_csv="Data/AI Trace Data/Earth_hourly.csv", workload_idx=4)

    # Patch reward if requested
    if args.reward_cls != "pue_tes":
        import pandas as pd
        from sinergym.utils.rewards import RL_Cost_Reward, RL_Green_Reward

        price = pd.read_csv("Data/prices/CAISO_NP15_2023_hourly.csv")["price_usd_per_mwh"].to_numpy()
        pv = pd.read_csv("Data/pv/CAISO_PaloAlto_PV_6MWp_hourly.csv")["power_kw"].to_numpy()
        kwargs = dict(
            temperature_variables=["air_temperature"],
            energy_variables=["Electricity:Facility"],
            ITE_variables=["ITE-CPU:InteriorEquipment:Electricity"],
            range_comfort_winter=(18.0, 25.0),
            range_comfort_summer=(18.0, 25.0),
            energy_weight=0.5,
            lambda_energy=1.0,
            lambda_temperature=1.0,  # M2-E3b: 3.0 → 1.0（对齐 run_m2_training.attach_reward）
            soc_variable="TES_SOC",
            soc_low=0.15, soc_high=0.85,
            soc_warn_low=0.30, soc_warn_high=0.70,
            lambda_soc=5.0, lambda_soc_warn=3.0,
            price_series=price, alpha=5e-4, beta=1.0,  # M2-E3b: 1e-6 → 5e-4（对齐 --alpha 默认）
        )
        if args.reward_cls == "rl_cost":
            cls = RL_Cost_Reward
        else:
            cls = RL_Green_Reward
            kwargs["pv_series"] = pv
            kwargs["c_pv"] = 0.0
            kwargs["pv_threshold_kw"] = 100.0

        # R1 fix (2026-04-19): gymnasium.Wrapper.__getattr__ forwards attribute
        # lookup to self.env, so hasattr(outer_wrapper, "reward_fn") is ALWAYS
        # True and the while-loop exits after zero iterations, patching the
        # outermost wrapper instead of EplusEnv. Result: env.unwrapped.reward_fn
        # remained the default (PUE_TES_Reward) and rl_cost/rl_green smoke runs
        # produced identical results. Patch directly on env.unwrapped (the
        # EplusEnv is the only layer that owns reward_fn).
        env.unwrapped.reward_fn = cls(**kwargs)
        assert isinstance(env.unwrapped.reward_fn, cls), (
            f"reward_fn patch did not land on EplusEnv, "
            f"got {type(env.unwrapped.reward_fn).__name__}"
        )

    # Post H2a/H2b/H2c/H2d: 20 + 6 + 3 + 3 + 9 = 41 dims (tech route §6.1).
    expected_dim = 41
    assert env.observation_space.shape == (expected_dim,), (
        f"Expected obs_dim={expected_dim}, got {env.observation_space.shape}"
    )
    assert env.action_space.shape == (6,), (
        f"Expected action_dim=6, got {env.action_space.shape}"
    )
    print(f"Env stack OK: obs_dim={expected_dim}, action_dim=6, reward={args.reward_cls}")

    obs, info = env.reset()
    assert obs.shape == (expected_dim,)
    print(f"reset obs.shape={obs.shape}, finite={np.all(np.isfinite(obs))}")

    rng = np.random.default_rng(42)
    for i in range(args.steps):
        a = rng.uniform(-1, 1, size=(6,)).astype(np.float32)
        obs, r, term, trunc, info = env.step(a)
        assert obs.shape == (expected_dim,)
        assert np.isfinite(r)
        # M5 fix (2026-04-19): EplusEnv.step does `info.update(rw_terms)`, so
        # reward terms are flattened into info (not nested under `terms`).  We
        # snapshot the known-M2 keys here to verify TES SoC is live.  If the
        # TES_SOC Schedule Value is not exported to obs_dict, PUE_TES_Reward
        # silently returns soc_value=None and the reward degrades to PUE+cost
        # only (losing the TES SoC guard).  Fail loudly here instead.
        reward_term_keys = (
            "soc_value", "soc_term", "soc_warn_term",
            "cost_term", "cost_usd_step", "mwh_step", "lmp_usd_per_mwh",
            "comfort_term", "comfort_extra_term", "effective_price_usd_per_mwh",
            "pv_kw",
        )
        terms_flat = {k: info[k] for k in reward_term_keys if k in info}
        soc_value = info.get("soc_value", None)

        summary = {
            "step": i + 1, "reward": round(float(r), 3),
            "wl_util": round(float(info.get("workload_utilization", 0)), 3),
            "wl_action": int(info.get("workload_action", 1)),
            "pv_kw": round(float(info.get("current_pv_kw", 0)), 1),
            "lmp": round(float(info.get("current_price_usd_per_mwh", 0)), 2),
            "soc": None if soc_value is None else round(float(soc_value), 4),
            "cost_usd": (None if "cost_usd_step" not in info
                         else round(float(info["cost_usd_step"]), 4)),
            "mwh": (None if "mwh_step" not in info
                    else round(float(info["mwh_step"]), 6)),
            "comfort_term": (None if "comfort_term" not in info
                             else round(float(info["comfort_term"]), 4)),
        }
        print(f"  {summary}")
        print(f"    reward_terms={terms_flat}")

        # Hard assertion — do not let a silent SoC-drop slip through.
        assert soc_value is not None, (
            "info['soc_value'] is None — TES SoC Schedule Value may not be "
            "exported to obs_dict.  Check TES wrapper + E+ output variables."
        )
        soc_float = float(soc_value)
        assert np.isfinite(soc_float) and 0.0 <= soc_float <= 1.0, (
            f"info['soc_value']={soc_float!r} out of [0,1] or non-finite; "
            "TES_SOC Schedule Value likely mis-scaled."
        )
        # Warn (not fail) on exactly-0 — SOC rarely legitimately hits 0 on step
        # 1 but might transiently; a persistent 0 across steps is the real red
        # flag and will show up as identical prints.
        if soc_float == 0.0:
            print("    [warn] soc_value == 0.0 — verify TES isn't empty at init.")

        # R1 fix (2026-04-19): prove the reward_fn patch landed by requiring
        # reward-class-specific info fields.  If env.unwrapped.reward_fn is
        # still PUE_TES_Reward these assertions fail loudly.
        if args.reward_cls == "rl_cost":
            for k in ("cost_term", "cost_usd_step", "mwh_step", "lmp_usd_per_mwh"):
                assert k in info, (
                    f"RL_Cost_Reward did not emit {k!r} into info — "
                    f"reward_fn patch likely failed (type="
                    f"{type(env.unwrapped.reward_fn).__name__})."
                )
        elif args.reward_cls == "rl_green":
            for k in (
                "cost_term", "cost_usd_step", "lmp_usd_per_mwh",
                "effective_price_usd_per_mwh", "pv_kw",
            ):
                assert k in info, (
                    f"RL_Green_Reward did not emit {k!r} into info — "
                    f"reward_fn patch likely failed (type="
                    f"{type(env.unwrapped.reward_fn).__name__})."
                )

    env.close()
    print("=" * 60)
    print(f"M2 ENV SMOKE PASSED ({args.reward_cls})")


if __name__ == "__main__":
    main()
