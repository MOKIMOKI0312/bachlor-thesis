"""测试 RL pipeline 的 IT 控制路径是否真的改变 EnergyPlus 内部 IT 负载。

设计：跳过 WorkloadWrapper，直接用 sinergym 底层 env 的 action[4]
（映射到 ITE_DRL → Schedule:Constant.ITE_Set），跑两次 24 步：
  Test A: action[4] = 0.05  （极低）
  Test B: action[4] = 0.80  （极高）
比较：
  - obs 中 ITE-CPU electricity 的差异
  - facility electricity 的差异

如果差异 > 30% → RL pipeline IT 控制有效（即使 P_2 重写，也有 fallback 路径）
如果差异 < 5% → IT 控制断开，agent 的 action[4] 在 EnergyPlus 端无效
"""
from __future__ import annotations
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import gymnasium as gym
import numpy as np

from sinergym.envs.tes_wrapper import TESIncrementalWrapper


def run_episode(label: str, action_4_value: float, n_steps: int = 24) -> dict:
    stamp = datetime.today().strftime("%Y-%m-%d_%H-%M-%S")
    env = gym.make(
        "Eplus-DC-Cooling-TES",
        env_name=f"{stamp}_ite_{label}",
        building_file=["DRL_DC_training.epJSON"],
        weather_files=["CHN_JS_Nanjing.582380_TMYx.2009-2023.epw"],
        config_params={"runperiod": (1, 1, 2025, 31, 12, 2025), "timesteps_per_hour": 1},
    )
    env = TESIncrementalWrapper(env, valve_idx=5, delta_max=0.20)
    # Note: NO WorkloadWrapper, NO PriceSignalWrapper etc. — keep it raw

    obs, info = env.reset()
    print(f"  obs.shape={obs.shape}, info keys: {list(info.keys())[:8]}...")

    obs_vars = env.get_wrapper_attr("observation_variables")
    print(f"  obs_vars[:20]: {obs_vars[:20]}")

    # Find indices for IT-related variables in obs
    idx_ite = None
    idx_fac = None
    for i, v in enumerate(obs_vars):
        if "CPU" in str(v) or "ITE" in str(v):
            idx_ite = i
        if "Facility" in str(v) or "facility" in str(v).lower():
            idx_fac = i
    print(f"  idx_ite={idx_ite}, idx_fac={idx_fac}")

    ite_vals, fac_vals = [], []
    for step_i in range(n_steps):
        a = np.zeros(6, dtype=np.float32)
        a[4] = action_4_value  # Force action[4] to fixed value
        obs, r, term, trunc, info = env.step(a)
        if idx_ite is not None: ite_vals.append(float(obs[idx_ite]))
        if idx_fac is not None: fac_vals.append(float(obs[idx_fac]))

    env.close()
    return {
        "label": label, "action_4": action_4_value, "n_steps": n_steps,
        "ite_min": min(ite_vals) if ite_vals else None,
        "ite_max": max(ite_vals) if ite_vals else None,
        "ite_mean": sum(ite_vals)/len(ite_vals) if ite_vals else None,
        "fac_min": min(fac_vals) if fac_vals else None,
        "fac_max": max(fac_vals) if fac_vals else None,
        "fac_mean": sum(fac_vals)/len(fac_vals) if fac_vals else None,
    }


def main():
    print("=" * 60)
    print("RL pipeline IT control verification")
    print("=" * 60)

    print("\n--- Test A: action[4] = 0.05 (low IT) ---")
    a = run_episode("low", 0.05, n_steps=24)
    print(f"  result: {a}")

    print("\n--- Test B: action[4] = 0.80 (high IT) ---")
    b = run_episode("high", 0.80, n_steps=24)
    print(f"  result: {b}")

    print("\n=== Comparison ===")
    if a["ite_mean"] and b["ite_mean"]:
        ratio_ite = b["ite_mean"] / a["ite_mean"]
        diff_ite_pct = 100 * (b["ite_mean"] - a["ite_mean"]) / a["ite_mean"]
        print(f"  ITE-CPU mean: low={a['ite_mean']:.3f}  high={b['ite_mean']:.3f}  ratio={ratio_ite:.3f}  diff={diff_ite_pct:+.1f}%")
    if a["fac_mean"] and b["fac_mean"]:
        ratio_fac = b["fac_mean"] / a["fac_mean"]
        diff_fac_pct = 100 * (b["fac_mean"] - a["fac_mean"]) / a["fac_mean"]
        print(f"  Facility mean: low={a['fac_mean']:.0f}  high={b['fac_mean']:.0f}  ratio={ratio_fac:.3f}  diff={diff_fac_pct:+.1f}%")

    print("\n=== Verdict ===")
    if a["ite_mean"] and b["ite_mean"]:
        if abs(diff_ite_pct) < 5:
            print("  ❌ IT 控制断开：agent action[4] 改变 0.05→0.80（16x），但 ITE-CPU 差异 < 5%")
            print("     根因（已在组件测试确认）：P_2 EMS 程序用 ITE_Now 自回归，不读 ITE_Set")
            return 1
        elif abs(diff_ite_pct) > 30:
            print("  ✅ IT 控制有效：ITE-CPU 差异 > 30%，RL agent 可以调度 IT 负载")
            return 0
        else:
            print(f"  ⚠️ 模糊结果：差异 {diff_ite_pct:.1f}%（介于 5-30%），可能 sinergym 有部分覆盖")
            return 2
    return 1


if __name__ == "__main__":
    sys.exit(main())
