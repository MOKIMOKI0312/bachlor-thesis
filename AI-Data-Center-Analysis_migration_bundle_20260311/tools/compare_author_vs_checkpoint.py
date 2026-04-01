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
    "Nanjing": "CHN_JS_Nanjing.582380_TMYx.2009-2023.epw",
    "Xuzhou": "CHN_JS_Xuzhou.580270_TMYx.2009-2023.epw",
    "Yinchuan": "CHN_NX_Yinchuan.536140_TMYx.2009-2023.epw",
}


def evaluate_once(
    root: Path,
    mean: np.ndarray,
    var: np.ndarray,
    model_path: Path,
    location: str,
    trace_name: str,
    label: str,
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
    experiment_name = f"compare-{label}-{location}-{trace_name}"

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
            action[4] = np.clip(util_rate[steps], 0.0, 1.0)
            obs, reward, terminated, truncated, info = env.step(action)
            rewards.append(float(reward))
            steps += 1
    finally:
        env.close()

    return {
        "label": label,
        "location": location,
        "trace": trace_name,
        "steps": steps,
        "total_reward": float(np.sum(rewards)),
        "mean_reward": float(np.mean(rewards)),
        "elapsed_seconds": time.perf_counter() - started,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--best-checkpoint", type=Path, required=True)
    args = parser.parse_args()

    root = args.root.resolve()
    workspace = args.workspace.resolve()
    best_checkpoint = args.best_checkpoint.resolve()

    eval_suite = [
        ("Sydney", "Earth"),
        ("Singapore", "Kalos"),
        ("Frankfurt", "PAI2020"),
        ("Lulea", "Saturn"),
    ]

    our_mean = np.loadtxt(workspace / "mean.txt", dtype="float")
    our_var = np.loadtxt(workspace / "var.txt", dtype="float")

    output_dir = workspace / "batch_eval_results"
    output_dir.mkdir(exist_ok=True)

    rows = []
    started = time.perf_counter()
    for location, trace in eval_suite:
        author_dir = root / "Data" / "log" / location
        author_result = evaluate_once(
            root,
            mean=np.loadtxt(author_dir / "mean_best.txt", dtype="float"),
            var=np.loadtxt(author_dir / "var_best.txt", dtype="float"),
            model_path=author_dir / "model.zip",
            location=location,
            trace_name=trace,
            label="author_pretrained",
        )
        ours_result = evaluate_once(
            root,
            mean=our_mean,
            var=our_var,
            model_path=best_checkpoint,
            location=location,
            trace_name=trace,
            label="our_best_checkpoint",
        )
        rows.extend([author_result, ours_result])

    df = pd.DataFrame(rows)
    df.to_csv(output_dir / "author_vs_our_best.csv", index=False)

    aggregate = (
        df.groupby("label")[["total_reward", "mean_reward", "elapsed_seconds"]]
        .mean()
        .reset_index()
        .sort_values("total_reward", ascending=False)
    )

    comparison = {}
    for location, trace in eval_suite:
        author_reward = df[(df["label"] == "author_pretrained") & (df["location"] == location) & (df["trace"] == trace)]["total_reward"].iloc[0]
        ours_reward = df[(df["label"] == "our_best_checkpoint") & (df["location"] == location) & (df["trace"] == trace)]["total_reward"].iloc[0]
        comparison[f"{location}:{trace}"] = {
            "author_total_reward": float(author_reward),
            "our_total_reward": float(ours_reward),
            "delta_our_minus_author": float(ours_reward - author_reward),
        }

    summary = {
        "eval_suite": [{"location": l, "trace": t} for l, t in eval_suite],
        "our_best_checkpoint": best_checkpoint.name,
        "aggregate": aggregate.to_dict(orient="records"),
        "per_case": comparison,
        "winner": aggregate.iloc[0]["label"],
        "total_batch_elapsed_seconds": time.perf_counter() - started,
    }
    (output_dir / "author_vs_our_best_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
