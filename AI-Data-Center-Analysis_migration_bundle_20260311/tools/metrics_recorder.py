"""
Metrics Recorder — 定时采样训练指标，记录历史时间序列。

每隔 N 秒从所有 seed 的 status.json 和 probe/episode_samples.jsonl 中
提取 ent_coef、critic_loss、actor_loss、reward、comfort_violation，
追加写入 CSV 文件，供后续因果分析。

用法:
    python tools/metrics_recorder.py --seeds 01 02 03 04 05 06 07 08 09 10 11 12 --interval 120
    python tools/metrics_recorder.py --interval 60 --output results/metrics_history.csv
"""

import argparse
import csv
import json
import time
from datetime import datetime
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def sample_seed(seed: str, job_prefix: str) -> dict:
    """从一个 seed 提取当前指标快照"""
    status_path = ROOT / "training_jobs" / f"{job_prefix}-seed{seed}" / "status.json"
    if not status_path.exists():
        return None

    try:
        status = json.loads(status_path.read_text(encoding="utf-8-sig"))
    except (json.JSONDecodeError, OSError):
        return None

    m = status.get("training_metrics", {})

    # 从 probe 读取最近 episode 的 reward 和 comfort
    run_dir = Path(status.get("workspace_path", ""))
    probe_path = run_dir / "probe" / "episode_samples.jsonl"
    last_reward = None
    last_comfort = None
    last_ep = None
    reward_last5 = []

    if probe_path.exists():
        try:
            lines = probe_path.read_text(encoding="utf-8").strip().split("\n")
            episodes = []
            for line in lines:
                if line.strip():
                    try:
                        episodes.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
            if episodes:
                last_ep = episodes[-1].get("episode_num", 0)
                last_reward = episodes[-1].get("cumulative_reward", None)
                last_comfort = episodes[-1].get("comfort_violation_time_pct", None)
                reward_last5 = [e["cumulative_reward"] for e in episodes[-5:]]
        except OSError:
            pass

    return {
        "seed": seed,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "epoch": time.time(),
        "episode": status.get("approx_episode", 0),
        "num_timesteps": status.get("num_timesteps", 0),
        "elapsed_seconds": status.get("elapsed_seconds", 0),
        "ent_coef": m.get("train/ent_coef", None),
        "critic_loss": m.get("train/critic_loss", None),
        "actor_loss": m.get("train/actor_loss", None),
        "ent_coef_loss": m.get("train/ent_coef_loss", None),
        "learning_rate": m.get("train/learning_rate", None),
        "n_updates": m.get("train/n_updates", None),
        "last_episode": last_ep,
        "last_reward": last_reward,
        "last_comfort_pct": last_comfort,
        "reward_mean_last5": float(np.mean(reward_last5)) if reward_last5 else None,
    }


def main():
    parser = argparse.ArgumentParser(description="Metrics Recorder")
    parser.add_argument("--seeds", nargs="+",
                        default=["01", "02", "03", "04", "05", "06",
                                 "07", "08", "09", "10", "11", "12"])
    parser.add_argument("--interval", type=int, default=120,
                        help="Sampling interval in seconds (default: 120)")
    parser.add_argument("--output", type=str, default=None,
                        help="Output CSV path (default: results/metrics_history.csv)")
    parser.add_argument("--job-prefix", type=str, default="e01_nanjing",
                        help="Job name prefix (default: e01_nanjing)")
    args = parser.parse_args()

    output_path = Path(args.output) if args.output else ROOT / "results" / "metrics_history.csv"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "seed", "timestamp", "epoch", "episode", "num_timesteps", "elapsed_seconds",
        "ent_coef", "critic_loss", "actor_loss", "ent_coef_loss",
        "learning_rate", "n_updates",
        "last_episode", "last_reward", "last_comfort_pct", "reward_mean_last5",
    ]

    # 如果文件已存在，追加；否则新建并写表头
    file_exists = output_path.exists() and output_path.stat().st_size > 0
    mode = "a" if file_exists else "w"

    sample_count = 0
    print(f"Metrics Recorder started")
    print(f"  Seeds: {args.seeds}")
    print(f"  Interval: {args.interval}s")
    print(f"  Output: {output_path}")
    print(f"  Job prefix: {args.job_prefix}")
    print(f"  Press Ctrl+C to stop\n")

    try:
        while True:
            rows = []
            for seed in args.seeds:
                data = sample_seed(seed, args.job_prefix)
                if data:
                    rows.append(data)

            if rows:
                with open(output_path, mode, newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    if not file_exists:
                        writer.writeheader()
                        file_exists = True
                    writer.writerows(rows)
                    mode = "a"  # 后续都是追加

                sample_count += 1
                now = datetime.now().strftime("%H:%M:%S")
                eps = [f"{r['seed']}:ep{r['episode']}" for r in rows]
                print(f"[{now}] Sample #{sample_count}: {', '.join(eps)}")

            time.sleep(args.interval)

    except KeyboardInterrupt:
        print(f"\nStopped. Total samples: {sample_count}")
        print(f"Data saved to: {output_path}")


if __name__ == "__main__":
    main()
