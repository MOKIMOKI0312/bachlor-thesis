"""
Rule-based baseline evaluation on Nanjing.

Uses Baseline_DC.epJSON which has fixed HVAC setpoints via SetpointManager:Scheduled.
No RL agent — constant 0.5 action passed in (EMS internally uses fixed schedules).

Usage:
    python tools/evaluate_baseline.py --trace Earth
"""

import argparse
import csv
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import gymnasium as gym
import numpy as np

from sinergym.utils.common import get_ids
from sinergym.utils.wrappers import LoggerWrapper


def evaluate(root: Path, trace_name: str) -> dict:
    if "Eplus-DC-Cooling" not in get_ids():
        raise RuntimeError("Eplus-DC-Cooling environment is not registered.")

    trace_path = root / "Data" / "AI Trace Data" / f"{trace_name}_hourly.csv"
    util_rate = np.loadtxt(trace_path, dtype="float")

    env = gym.make(
        "Eplus-DC-Cooling",
        env_name=f"eval-baseline-{trace_name}",
        building_file="Baseline_DC.epJSON",
        weather_files="CHN_JS_Nanjing.582380_TMYx.2009-2023.epw",
        config_params={"runperiod": (1, 1, 2025, 31, 12, 2025), "timesteps_per_hour": 1},
        evaluation_flag=1,
    )
    env = LoggerWrapper(
        env,
        monitor_header=["timestep"]
        + env.get_wrapper_attr("observation_variables")
        + env.get_wrapper_attr("action_variables")
        + ["time (hours)", "reward", "energy_term", "ITE_term", "comfort_term", "terminated", "truncated"],
    )

    workspace_post = Path(env.get_wrapper_attr("workspace_path"))

    started = time.perf_counter()
    obs, _ = env.reset()
    terminated = truncated = False
    step = 0
    total_reward = 0.0

    # Use constant middle action (0.5 for each dim). IT utilization (action[4]) is overridden with trace.
    constant_action = np.full(env.action_space.shape, 0.5, dtype=np.float32)

    while not (terminated or truncated):
        action = constant_action.copy()
        if step < len(util_rate):
            action[4] = float(np.clip(util_rate[step], 0.0, 1.0))
        obs, reward, terminated, truncated, _ = env.step(action)
        total_reward += float(reward)
        step += 1

    env.close()

    monitor_path = workspace_post / "episode-001" / "monitor.csv"
    with open(monitor_path, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    total_facility_J = sum(float(r["Electricity:Facility"] or 0) for r in rows)
    total_ite_J = sum(float(r["ITE-CPU:InteriorEquipment:Electricity"] or 0) for r in rows)
    temps = [float(r["air_temperature"]) for r in rows if r.get("air_temperature")]
    # Exclude warm-up step (first row)
    temps_stable = temps[1:] if len(temps) > 1 else temps
    comfort_violations = sum(1 for t in temps_stable if t > 25.0)

    pue = total_facility_J / total_ite_J if total_ite_J > 0 else float("nan")
    comfort_pct = comfort_violations / len(temps_stable) * 100 if temps_stable else 0

    return {
        "label": "rule_based_baseline",
        "building": "Baseline_DC.epJSON",
        "trace": trace_name,
        "steps": step,
        "total_reward": total_reward,
        "total_facility_MWh": total_facility_J / 3.6e9,
        "total_ite_MWh": total_ite_J / 3.6e9,
        "pue": pue,
        "comfort_violation_pct": comfort_pct,
        "mean_temperature_C": float(np.mean(temps_stable)) if temps_stable else None,
        "max_temperature_C_with_warmup": float(np.max(temps)) if temps else None,
        "max_temperature_C_stable": float(np.max(temps_stable)) if temps_stable else None,
        "p95_temperature_C": float(np.percentile(temps_stable, 95)) if temps_stable else None,
        "monitor_csv": str(monitor_path),
        "elapsed_seconds": time.perf_counter() - started,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trace", default="Earth")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    result = evaluate(ROOT, args.trace)
    print(json.dumps(result, indent=2))

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
