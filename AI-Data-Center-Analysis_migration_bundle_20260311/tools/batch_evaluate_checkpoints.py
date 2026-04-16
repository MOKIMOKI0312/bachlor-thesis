import argparse
import json
import time
from pathlib import Path

import gymnasium as gym
import numpy as np
import pandas as pd
from stable_baselines3 import SAC

from sinergym.utils.wrappers import LoggerWrapper, NormalizeObservation


class SimpleCSVLogger:
    def __init__(self, monitor_header, progress_header, log_progress_file, log_file=None, flag=True):
        from sinergym.utils.logger import CSVLogger

        self._delegate = CSVLogger(monitor_header, progress_header, log_progress_file, log_file, flag)

    def __getattr__(self, name):
        return getattr(self._delegate, name)


WEATHER_MAP = {
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


def evaluate_once(
    root: Path,
    mean: np.ndarray,
    var: np.ndarray,
    model_path: Path,
    location: str,
    trace_name: str,
) -> dict:
    from sinergym.utils.common import get_ids

    if "Eplus-DC-Cooling" not in get_ids():
        raise RuntimeError("Eplus-DC-Cooling environment is not registered.")

    trace_path = root / "Data" / "AI Trace Data" / f"{trace_name}_hourly.csv"
    building_path = root / "Data" / "buildings" / "DRL_DC_evaluation.epJSON"
    weather_path = root / "Data" / "weather" / WEATHER_MAP[location]
    util_rate = np.loadtxt(trace_path, dtype="float")
    model = SAC.load(str(model_path))

    config = {"runperiod": (1, 1, 2025, 31, 12, 2025), "timesteps_per_hour": 1}
    experiment_name = f"batch-eval-{model_path.stem}-{location}-{trace_name}"

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
    rewards = []
    terminated = truncated = False
    steps = 0

    try:
        while not (terminated or truncated):
            action, _ = model.predict(obs, deterministic=True)
            action[5] = util_rate[steps]
            obs, reward, terminated, truncated, info = env.step(action)
            rewards.append(float(reward))
            steps += 1
    finally:
        env.close()

    return {
        "location": location,
        "trace": trace_name,
        "steps": steps,
        "total_reward": float(np.sum(rewards)),
        "mean_reward": float(np.mean(rewards)),
        "elapsed_seconds": time.perf_counter() - started,
    }


def episode_from_name(path: Path) -> int:
    stem = path.stem
    if stem.endswith("_steps"):
        step_str = stem.split("_")[-2]
    else:
        step_str = stem.split("_")[-1]
    timesteps = int(step_str)
    return round(timesteps / 8759)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    args = parser.parse_args()

    root = args.root.resolve()
    workspace = args.workspace.resolve()
    checkpoints_dir = workspace / "checkpoints"
    mean = np.loadtxt(workspace / "mean.txt", dtype="float")
    var = np.loadtxt(workspace / "var.txt", dtype="float")

    candidates = sorted(checkpoints_dir.glob("codex_300ep_model_*_steps.zip"), key=episode_from_name)
    candidates.append(workspace / "codex_300ep_model.zip")

    eval_suite = [
        ("Sydney", "Earth"),
        ("Singapore", "Kalos"),
        ("Frankfurt", "PAI2020"),
        ("Lulea", "Saturn"),
    ]

    output_dir = workspace / "batch_eval_results"
    output_dir.mkdir(exist_ok=True)

    rows = []
    started = time.perf_counter()
    for model_path in candidates:
        model_label = model_path.name
        episode = 300 if model_path.name == "codex_300ep_model.zip" else episode_from_name(model_path)
        run_rewards = []
        run_means = []
        total_eval_time = 0.0
        for location, trace in eval_suite:
            result = evaluate_once(root, mean, var, model_path, location, trace)
            total_eval_time += result["elapsed_seconds"]
            run_rewards.append(result["total_reward"])
            run_means.append(result["mean_reward"])
            rows.append(
                {
                    "model_file": model_label,
                    "episode": episode,
                    "location": location,
                    "trace": trace,
                    "total_reward": result["total_reward"],
                    "mean_reward": result["mean_reward"],
                    "steps": result["steps"],
                    "eval_elapsed_seconds": result["elapsed_seconds"],
                }
            )

        rows.append(
            {
                "model_file": model_label,
                "episode": episode,
                "location": "__aggregate__",
                "trace": "__aggregate__",
                "total_reward": float(np.mean(run_rewards)),
                "mean_reward": float(np.mean(run_means)),
                "steps": int(np.mean([8759, 8759, 8759, 8759])),
                "eval_elapsed_seconds": total_eval_time,
            }
        )

    df = pd.DataFrame(rows)
    df.to_csv(output_dir / "checkpoint_eval_table.csv", index=False)

    aggregate = df[df["location"] == "__aggregate__"].sort_values("total_reward", ascending=False).reset_index(drop=True)
    best = aggregate.iloc[0].to_dict()
    summary = {
        "eval_suite": [{"location": l, "trace": t} for l, t in eval_suite],
        "models_evaluated": int(len(aggregate)),
        "best_model_file": best["model_file"],
        "best_episode": int(best["episode"]),
        "best_average_total_reward": float(best["total_reward"]),
        "best_average_mean_reward": float(best["mean_reward"]),
        "total_batch_elapsed_seconds": time.perf_counter() - started,
        "top5": aggregate.head(5).to_dict(orient="records"),
    }
    (output_dir / "checkpoint_eval_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
