import argparse
import json
import time
from pathlib import Path

import gymnasium as gym
import numpy as np
from stable_baselines3 import SAC

from sinergym.utils.wrappers import LoggerWrapper, NormalizeObservation


class SimpleCSVLogger:
    def __init__(self, monitor_header, progress_header, log_progress_file, log_file=None, flag=True):
        from sinergym.utils.logger import CSVLogger

        self._delegate = CSVLogger(monitor_header, progress_header, log_progress_file, log_file, flag)

    def __getattr__(self, name):
        return getattr(self._delegate, name)


def run_example(root: Path, location: str, trace_name: str, max_steps: int | None, full_year: bool) -> dict:
    from sinergym.utils.common import get_ids

    if "Eplus-DC-Cooling" not in get_ids():
        raise RuntimeError("Eplus-DC-Cooling environment is not registered.")

    weather_map = {
        "Sydney": "AUS_NSW_Sydney.Intl.AP.947670_TMYx.2009-2023.epw",
        "Frankfurt": "DEU_HE_Frankfurt.AP.106370_TMYx.2009-2023.epw",
        "Singapore": "SGP_SG_Singapore-Changi.Intl.AP.486980_TMYx.2009-2023.epw",
        "Lulea": "SWE_NB_Lulea.AP.021860_TMYx.2009-2023.epw",
        "SiliconValley": "USA_CA_San.Francisco.Intl.AP.724940_TMYx.2009-2023.epw",
        "DesMoines": "USA_IA_Des.Moines.Intl.AP.725460_TMYx.2009-2023.epw",
        "Omaha": "USA_NE_Omaha-Eppley.AF.Intl.AP.725500_TMYx.2009-2023.epw",
        "NewYork": "USA_NY_New.York-Kennedy.Intl.AP.744860_TMYx.2009-2023.epw",
        "Dallas": "USA_TX_Dallas-Fort.Worth.Intl.AP.722590_TMYx.2009-2023.epw",
        "NorthVirginia": "USA_VA_Dulles-Washington.Dulles.Intl.AP.724030_TMYx.2009-2023.epw",
    }

    if location not in weather_map:
        raise ValueError(f"Unsupported location: {location}")

    data_dir = root / "Data"
    trace_path = data_dir / "AI Trace Data" / f"{trace_name}_hourly.csv"
    mean_path = data_dir / "log" / location / "mean_best.txt"
    var_path = data_dir / "log" / location / "var_best.txt"
    model_path = data_dir / "log" / location / "model.zip"
    building_path = data_dir / "buildings" / "DRL_DC_evaluation.epJSON"
    weather_path = data_dir / "weather" / weather_map[location]

    util_rate = np.loadtxt(trace_path, dtype="float")
    mean = np.loadtxt(mean_path, dtype="float")
    var = np.loadtxt(var_path, dtype="float")
    model = SAC.load(str(model_path))

    config = {"runperiod": (1, 1, 2025, 31, 12, 2025), "timesteps_per_hour": 1}
    run_name = "year" if full_year else f"{max_steps}steps"
    experiment_name = f"codex-{location}-{trace_name}-{run_name}"

    env = gym.make(
        "Eplus-DC-Cooling",
        env_name=experiment_name,
        building_file=str(building_path.name),
        weather_files=str(weather_path.name),
        config_params=config,
        evaluation_flag=1,
    )
    env = NormalizeObservation(env, mean=mean, var=var, automatic_update=False)
    env = LoggerWrapper(
        env,
        logger_class=SimpleCSVLogger,
        monitor_header=["timestep"]
        + env.get_wrapper_attr("observation_variables")
        + env.get_wrapper_attr("action_variables")
        + ["time (hours)", "reward", "energy_term", "comfort_term", "terminated", "truncated"],
    )

    started = time.perf_counter()
    obs, info = env.reset()
    terminated = truncated = False
    rewards = []
    steps = 0
    last_info = info

    try:
        while not (terminated or truncated):
            action, _ = model.predict(obs, deterministic=True)
            action[5] = util_rate[steps]
            obs, reward, terminated, truncated, info = env.step(action)
            rewards.append(float(reward))
            steps += 1
            last_info = info
            if max_steps is not None and steps >= max_steps:
                break
    finally:
        env.close()

    result = {
        "location": location,
        "trace": trace_name,
        "steps": steps,
        "terminated": bool(terminated),
        "truncated": bool(truncated),
        "mean_reward": float(np.mean(rewards)) if rewards else None,
        "total_reward": float(np.sum(rewards)) if rewards else None,
        "elapsed_seconds": time.perf_counter() - started,
        "workspace_path": env.get_wrapper_attr("workspace_path"),
        "last_info_keys": sorted(last_info.keys()),
    }
    print(json.dumps(result, indent=2))
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--location", default="Sydney")
    parser.add_argument("--trace", default="Earth")
    parser.add_argument("--max-steps", type=int, default=24)
    parser.add_argument("--full-year", action="store_true")
    args = parser.parse_args()

    max_steps = None if args.full_year else args.max_steps
    run_example(args.root, args.location, args.trace, max_steps=max_steps, full_year=args.full_year)


if __name__ == "__main__":
    main()
