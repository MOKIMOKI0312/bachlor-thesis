"""
Training Probe - 训练探针
监控多 seed 并行训练的进度、收敛性和异常检测。

用法:
    python tools/training_probe.py --seeds 01 02 03 04
    python tools/training_probe.py --seeds 01 02 03 04 --watch 60  # 每60秒刷新
    python tools/training_probe.py --seeds 01 02 03 04 --report    # 输出完整报告到 JSON
"""

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def load_status(seed: str) -> Optional[Dict[str, Any]]:
    """读取 seed 的 status.json"""
    path = ROOT / "training_jobs" / f"e0_nanjing-seed{seed}" / "status.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (json.JSONDecodeError, OSError):
        return None


def load_episode_samples(run_dir: Path) -> List[Dict[str, Any]]:
    """读取 probe/episode_samples.jsonl"""
    path = run_dir / "probe" / "episode_samples.jsonl"
    if not path.exists():
        return []
    samples = []
    for line in path.read_text(encoding="utf-8").strip().split("\n"):
        if line.strip():
            try:
                samples.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return samples


def load_progress_csv(run_dir: Path) -> List[Dict[str, Any]]:
    """读取 progress.csv"""
    path = run_dir / "progress.csv"
    if not path.exists():
        return []
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        header = f.readline().strip().split(",")
        for line in f:
            vals = line.strip().split(",")
            if len(vals) == len(header):
                row = {}
                for k, v in zip(header, vals):
                    try:
                        row[k] = float(v)
                    except ValueError:
                        row[k] = v
                rows.append(row)
    return rows


def detect_anomalies(episodes: List[Dict[str, Any]]) -> List[str]:
    """检测训练异常"""
    warnings = []
    if len(episodes) < 5:
        return warnings

    rewards = [e["cumulative_reward"] for e in episodes]

    # 1. 策略崩坏检测：reward 突然下跌超过 50%
    for i in range(5, len(rewards)):
        window_avg = np.mean(rewards[max(0, i - 5):i])
        if window_avg != 0 and rewards[i] < window_avg * 1.5:  # reward 是负值，所以 *1.5 意味着更差
            drop_pct = (rewards[i] - window_avg) / abs(window_avg) * 100
            if drop_pct < -50:
                warnings.append(
                    f"POLICY COLLAPSE at ep {episodes[i]['episode_num']}: "
                    f"reward={rewards[i]:.1f} vs avg={window_avg:.1f} ({drop_pct:.0f}%)"
                )

    # 2. Comfort violation 过高
    recent = episodes[-5:]
    avg_violation = np.mean([e.get("comfort_violation_time_pct", 0) for e in recent])
    if avg_violation > 20:
        warnings.append(f"HIGH COMFORT VIOLATION: recent 5-ep avg = {avg_violation:.1f}%")

    # 3. Reward 停滞（最近 20 episode 无改善）
    if len(rewards) >= 20:
        first_half = np.mean(rewards[-20:-10])
        second_half = np.mean(rewards[-10:])
        if abs(second_half - first_half) / (abs(first_half) + 1e-8) < 0.02:
            warnings.append(
                f"REWARD STAGNATION: last 20 ep change < 2% "
                f"({first_half:.1f} → {second_half:.1f})"
            )

    # 4. 最佳 reward 追踪
    best_idx = int(np.argmax(rewards))  # 最大值（最不负的）
    best_ep = episodes[best_idx]["episode_num"]
    if len(episodes) - best_idx > 30:
        warnings.append(
            f"BEST REWARD at ep {best_ep} ({rewards[best_idx]:.1f}), "
            f"no improvement for {len(episodes) - best_idx} episodes"
        )

    return warnings


def format_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    return f"{h}h{m:02d}m"


def print_dashboard(seeds: List[str]):
    """打印训练仪表盘"""
    total_target = 300 * 8759  # 2,627,700 steps

    print(f"\n{'=' * 90}")
    print(f"  E0 Nanjing Training Dashboard  |  {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'=' * 90}")

    # Header
    print(f"\n{'Seed':<8} {'Episode':<10} {'Steps':<10} {'Progress':<10} "
          f"{'Elapsed':<9} {'ETA':<9} {'Reward':<12} {'Best':<12} {'Comfort%':<10}")
    print("-" * 90)

    all_episodes = {}
    for seed in seeds:
        status = load_status(seed)
        if status is None:
            print(f"seed{seed:<4} {'NO DATA':<10}")
            continue

        run_dir = Path(status.get("workspace_path", ""))
        episodes = load_episode_samples(run_dir)
        all_episodes[seed] = episodes

        ep = status.get("approx_episode", 0)
        steps = status.get("num_timesteps", 0)
        elapsed = status.get("elapsed_seconds", 0)
        finished = status.get("finished", False)
        metrics = status.get("training_metrics", {})

        # Progress
        pct = steps / total_target * 100 if total_target > 0 else 0
        eta = (elapsed / (pct / 100) - elapsed) if pct > 0 else 0

        # Recent reward (from episodes)
        if episodes:
            recent_reward = episodes[-1]["cumulative_reward"]
            best_reward = max(e["cumulative_reward"] for e in episodes)
            recent_comfort = episodes[-1].get("comfort_violation_time_pct", 0)
        else:
            recent_reward = best_reward = 0
            recent_comfort = 0

        status_icon = "DONE" if finished else f"{pct:.0f}%"

        print(f"seed{seed:<4} {ep:<10} {steps:<10} {status_icon:<10} "
              f"{format_time(elapsed):<9} {format_time(eta):<9} "
              f"{recent_reward:<12.1f} {best_reward:<12.1f} {recent_comfort:<10.1f}")

    # Anomaly detection
    print(f"\n{'=' * 90}")
    print("  Anomaly Detection")
    print("-" * 90)
    any_warning = False
    for seed, episodes in all_episodes.items():
        warnings = detect_anomalies(episodes)
        for w in warnings:
            print(f"  [seed{seed}] {w}")
            any_warning = True
    if not any_warning:
        print("  All seeds nominal.")

    # Training metrics
    print(f"\n{'=' * 90}")
    print("  SAC Metrics (latest)")
    print("-" * 90)
    print(f"{'Seed':<8} {'Actor Loss':<14} {'Critic Loss':<14} {'Ent Coef':<12} {'Updates':<10}")
    print("-" * 58)
    for seed in seeds:
        status = load_status(seed)
        if status and "training_metrics" in status:
            m = status["training_metrics"]
            print(f"seed{seed:<4} {m.get('train/actor_loss', 'N/A'):<14.2f} "
                  f"{m.get('train/critic_loss', 'N/A'):<14.2f} "
                  f"{m.get('train/ent_coef', 'N/A'):<12.4f} "
                  f"{m.get('train/n_updates', 'N/A'):<10}")

    # Reward trend (last 10 episodes per seed)
    print(f"\n{'=' * 90}")
    print("  Reward Trend (last 10 episodes)")
    print("-" * 90)
    for seed, episodes in all_episodes.items():
        if len(episodes) >= 2:
            recent = episodes[-10:]
            rewards = [e["cumulative_reward"] for e in recent]
            ep_nums = [e["episode_num"] for e in recent]
            trend = "↑" if len(rewards) > 1 and rewards[-1] > rewards[0] else "↓"
            bars = "".join(["█" if r > np.median(rewards) else "▄" for r in rewards])
            print(f"  seed{seed}: ep{ep_nums[0]}-{ep_nums[-1]}  "
                  f"[{min(rewards):.0f} ~ {max(rewards):.0f}] {trend}  {bars}")

    print(f"\n{'=' * 90}\n")


def generate_report(seeds: List[str]) -> Dict[str, Any]:
    """生成完整训练报告 JSON"""
    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "seeds": {},
        "summary": {},
    }

    all_best = []
    for seed in seeds:
        status = load_status(seed)
        if status is None:
            continue

        run_dir = Path(status.get("workspace_path", ""))
        episodes = load_episode_samples(run_dir)
        warnings = detect_anomalies(episodes)

        rewards = [e["cumulative_reward"] for e in episodes] if episodes else []
        best_reward = max(rewards) if rewards else None
        best_ep = episodes[int(np.argmax(rewards))]["episode_num"] if rewards else None

        seed_report = {
            "run_dir": str(run_dir),
            "approx_episode": status.get("approx_episode", 0),
            "num_timesteps": status.get("num_timesteps", 0),
            "elapsed_seconds": status.get("elapsed_seconds", 0),
            "finished": status.get("finished", False),
            "total_episodes": len(episodes),
            "best_reward": best_reward,
            "best_episode": best_ep,
            "last_reward": rewards[-1] if rewards else None,
            "mean_last10_reward": float(np.mean(rewards[-10:])) if len(rewards) >= 10 else None,
            "warnings": warnings,
            "training_metrics": status.get("training_metrics", {}),
        }
        report["seeds"][f"seed{seed}"] = seed_report
        if best_reward is not None:
            all_best.append((seed, best_reward, best_ep))

    if all_best:
        all_best.sort(key=lambda x: x[1], reverse=True)
        report["summary"]["best_seed"] = all_best[0][0]
        report["summary"]["best_reward"] = all_best[0][1]
        report["summary"]["best_episode"] = all_best[0][2]
        report["summary"]["median_best_reward"] = float(np.median([b[1] for b in all_best]))

    return report


def main():
    parser = argparse.ArgumentParser(description="Training Probe")
    parser.add_argument("--seeds", nargs="+", default=["01", "02", "03", "04"])
    parser.add_argument("--watch", type=int, help="Auto-refresh interval in seconds")
    parser.add_argument("--report", action="store_true", help="Output full report as JSON")
    args = parser.parse_args()

    if args.report:
        report = generate_report(args.seeds)
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return

    if args.watch:
        try:
            while True:
                # Clear screen
                print("\033[2J\033[H", end="")
                print_dashboard(args.seeds)
                print(f"  Auto-refresh every {args.watch}s. Press Ctrl+C to stop.")
                time.sleep(args.watch)
        except KeyboardInterrupt:
            print("\nStopped.")
    else:
        print_dashboard(args.seeds)


if __name__ == "__main__":
    main()
