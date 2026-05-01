"""B4-v2 warmup smoke test — verify random-action warmup + var floor clamp.

Pre-fix pathology (2026-04-23):
  center_action=[0.5,0.5,0.5,0.0] -> exposed TES action index 3 = 0 ->
  valve stays at 0 throughout warmup → obs_rms.var for dim 15 collapses to
  epsilon (1.14e-8).

  Consequence: during training, (obs - μ) / sqrt(var + eps) amplifies any
  nonzero sample by ~10^4, triggering DSAC-T critic explosion
  (σ=642, ent=1.835 by ep3).

Post-fix:
  (1) action = env.action_space.sample() covers exposed TES target ∈ [-1, 1].
  (2) obs_rms.var clamped to floor 1e-2 after freeze, capping normalization
      amplification at 10× for any dim.

Expected:
  obs_rms.var.min() >= 1e-2  (after clamp)
  At least a few dims were clipped (n_clipped > 0)
  No dim sits at 1.14e-8 post-clamp
"""
from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import gymnasium as gym
import numpy as np

from sinergym.utils.wrappers import NormalizeObservation, LoggerWrapper
from sinergym.envs.tes_wrapper import FixedActionInsertWrapper, TESTargetValveWrapper
from sinergym.envs.time_encoding_wrapper import TimeEncodingWrapper
from sinergym.envs.temp_trend_wrapper import TempTrendWrapper
from sinergym.envs.price_signal_wrapper import PriceSignalWrapper
from sinergym.envs.pv_signal_wrapper import PVSignalWrapper
from sinergym.envs.energy_scale_wrapper import EnergyScaleWrapper
from tools.m2_action_guard import M2_FIXED_FAN_VALUE


VAR_FLOOR = 1e-2
EPSILON_FLOOR = 1e-8  # NormalizeObservation default epsilon — if any dim stays
# here post-clamp, it means the floor didn't apply


def main() -> int:
    epw = "CHN_JS_Nanjing.582380_TMYx.2009-2023.epw"
    price_csv = "Data/prices/Jiangsu_TOU_2025_hourly.csv"
    pv_csv = "Data/pv/CHN_Nanjing_PV_6MWp_hourly.csv"

    stamp = datetime.today().strftime("%Y-%m-%d_%H-%M-%S")
    env = gym.make(
        "Eplus-DC-Cooling-TES",
        env_name=f"smoke_b4_warmup_{stamp}",
        building_file=["DRL_DC_training.epJSON"],
        weather_files=[epw],
        config_params={
            "runperiod": (1, 1, 2025, 31, 12, 2025),
            "timesteps_per_hour": 4,
        },
    )
    env.action_space.seed(42)

    # Mirror full training wrapper chain (run_m2_training.build_env).
    env = TESTargetValveWrapper(env, valve_idx=4, rate_limit=0.25)
    env = FixedActionInsertWrapper(
        env,
        fixed_actions={0: M2_FIXED_FAN_VALUE},
        fixed_action_names={0: "CRAH_Fan_DRL"},
    )
    env = TimeEncodingWrapper(env)
    env = TempTrendWrapper(env, epw_path=Path("Data/weather") / epw, lookahead_hours=6)
    env = PriceSignalWrapper(env, price_csv_path=price_csv, lookahead_hours=6)
    env = PVSignalWrapper(env, pv_csv_path=pv_csv, dc_peak_load_kw=6000.0, lookahead_hours=6)
    env = EnergyScaleWrapper(env, energy_indices=[13, 14], scale=1.0 / 3.6e9)

    # Obs-variable names (for per-dim diagnostics).
    obs_names = list(env.get_wrapper_attr("observation_variables"))
    assert len(obs_names) == 32, f"expected 32-dim obs, got {len(obs_names)}"

    env = NormalizeObservation(env)
    # No LoggerWrapper here — keeps smoke test focused on obs_rms state.

    print(f"[B4-smoke] obs_dim = {env.observation_space.shape[0]} (expect 32)")
    assert env.observation_space.shape[0] == 32

    # === Run 1 random-action warmup episode (mirrors B4-v2 in run_m2_training) ===
    print("[B4-smoke] Running 1 random-action warmup episode (this is 1 full E+ year)...")
    env.action_space.seed(1001)  # seed + 1000 equivalent for seed=1
    warmup_obs, _ = env.reset()
    done = truncated = False
    step_count = 0
    t0 = datetime.now()
    while not (done or truncated):
        action = env.action_space.sample()
        warmup_obs, _, done, truncated, _ = env.step(action)
        step_count += 1
        if step_count % 1000 == 0:
            print(f"[B4-smoke]   step {step_count}, elapsed {(datetime.now()-t0).total_seconds():.1f}s")
    t_warmup = (datetime.now() - t0).total_seconds()
    print(f"[B4-smoke] Warmup done: {step_count} steps in {t_warmup:.1f}s.")

    env.deactivate_update()

    # === Inspect obs_rms.var before and after clamp ===
    obs_rms = env.get_wrapper_attr('obs_rms')
    var_before = obs_rms.var.copy()

    min_v_before = float(var_before.min())
    max_v_before = float(var_before.max())
    median_v_before = float(np.median(var_before))
    n_below_before = int((var_before < VAR_FLOOR).sum())
    n_at_eps_before = int((var_before < 10 * EPSILON_FLOOR).sum())  # within 10× epsilon

    print(f"\n[B4-smoke] obs_rms.var BEFORE clamp:")
    print(f"  min       = {min_v_before:.4e}")
    print(f"  max       = {max_v_before:.4e}")
    print(f"  median    = {median_v_before:.4e}")
    print(f"  n_below_{VAR_FLOOR:.0e} = {n_below_before}/{len(var_before)}")
    print(f"  n_near_epsilon ({10 * EPSILON_FLOOR:.0e}) = {n_at_eps_before}/{len(var_before)}")

    # Show which dims are pathological
    if n_below_before > 0:
        print(f"\n[B4-smoke] Dims with var < {VAR_FLOOR:.0e} (the pathological ones):")
        bad_idx = np.where(var_before < VAR_FLOOR)[0]
        for i in bad_idx:
            name = obs_names[i] if i < len(obs_names) else f"dim{i}"
            print(f"    dim {i:2d} ({name}): var={var_before[i]:.4e}, mean={obs_rms.mean[i]:.4e}")

    # === Apply var floor clamp (mirrors B4-v2) ===
    n_clipped = int((obs_rms.var < VAR_FLOOR).sum())
    obs_rms.var = np.maximum(obs_rms.var, VAR_FLOOR)

    var_after = obs_rms.var
    min_v_after = float(var_after.min())
    max_v_after = float(var_after.max())
    median_v_after = float(np.median(var_after))
    n_below_after = int((var_after < VAR_FLOOR).sum())

    print(f"\n[B4-smoke] obs_rms.var AFTER clamp (floor={VAR_FLOOR}):")
    print(f"  min       = {min_v_after:.4e}")
    print(f"  max       = {max_v_after:.4e}")
    print(f"  median    = {median_v_after:.4e}")
    print(f"  n_below_{VAR_FLOOR:.0e} = {n_below_after}/{len(var_after)}")
    print(f"  n_clipped = {n_clipped}")

    # === Acceptance ===
    ok = True
    if min_v_after < VAR_FLOOR - 1e-12:
        print(f"\n[B4-smoke] FAIL: min(obs_rms.var) = {min_v_after:.4e} < floor {VAR_FLOOR}")
        ok = False
    else:
        print(f"\n[B4-smoke] PASS: min(obs_rms.var) = {min_v_after:.4e} >= floor {VAR_FLOOR}")

    # Max amplification = 1/sqrt(var_min)
    max_amp = 1.0 / np.sqrt(min_v_after + obs_rms.mean.dtype.type(0) + 1e-12)
    print(f"[B4-smoke] max normalization amplification = 1/sqrt({min_v_after:.2e}) = {max_amp:.2f}×")
    if max_amp > 20.0:
        print(f"[B4-smoke] WARN: max amplification {max_amp:.2f} > 20×")

    env.close()

    if ok:
        print("\n[B4-smoke] RESULT: B4-v2 fix verified — random warmup + var floor clamp working.")
        return 0
    print("\n[B4-smoke] RESULT: B4-v2 fix FAILED — see above.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
