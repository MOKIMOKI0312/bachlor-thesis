"""
Training Watchdog — 每隔 N 秒检查训练状态。
如果超过半数 seed 发散（ent_coef > 1.0 或 critic_loss > 5000），
自动终止所有训练进程并生成报告。

用法:
    python tools/training_watchdog.py --prefix e03_nanjing --interval 7200
"""

import argparse
import csv
import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def check_seed(seed: str, prefix: str):
    """检查单个 seed 的健康状态"""
    status_path = ROOT / "training_jobs" / f"{prefix}-seed{seed}" / "status.json"
    if not status_path.exists():
        return None

    try:
        status = json.loads(status_path.read_text(encoding="utf-8-sig"))
    except (json.JSONDecodeError, OSError):
        return None

    m = status.get("training_metrics", {})
    ep = status.get("approx_episode", 0)
    ent = m.get("train/ent_coef", 0)
    critic = m.get("train/critic_loss", 0)
    finished = status.get("finished", False)

    # Read probe for reward
    run_dir = Path(status.get("workspace_path", ""))
    probe_path = run_dir / "probe" / "episode_samples.jsonl"
    last_reward = None
    best_reward = None
    last_comfort = None

    if probe_path.exists():
        try:
            episodes = []
            for line in probe_path.read_text(encoding="utf-8").strip().split("\n"):
                if line.strip():
                    try:
                        episodes.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
            if episodes:
                rewards = [e["cumulative_reward"] for e in episodes]
                last_reward = rewards[-1]
                best_reward = max(rewards)
                last_comfort = episodes[-1].get("comfort_violation_time_pct", 0)
        except OSError:
            pass

    # Health classification
    if ent > 1.0 or critic > 5000:
        health = "DIVERGED"
    elif ent > 0.3 or critic > 1000:
        health = "UNSTABLE"
    else:
        health = "HEALTHY"

    return {
        "seed": seed,
        "episode": ep,
        "ent_coef": ent,
        "critic_loss": critic,
        "last_reward": last_reward,
        "best_reward": best_reward,
        "last_comfort": last_comfort,
        "health": health,
        "finished": finished,
    }


def kill_all_training(prefix: str, seeds: list):
    """终止所有训练进程"""
    killed = 0
    for seed in seeds:
        manifest_path = ROOT / "training_jobs" / f"{prefix}-seed{seed}" / "manifest.json"
        if manifest_path.exists():
            try:
                manifest = json.loads(manifest_path.read_text())
                pid = manifest.get("pid")
                if pid:
                    if sys.platform == "win32":
                        subprocess.run(
                            ["taskkill", "/PID", str(pid), "/F", "/T"],
                            capture_output=True,
                        )
                    else:
                        os.kill(pid, signal.SIGTERM)
                    killed += 1
            except (json.JSONDecodeError, OSError, ProcessLookupError):
                pass
    return killed


def write_report(results: list, prefix: str, reason: str):
    """写入 watchdog 报告"""
    report_path = ROOT / "results" / f"watchdog_report_{prefix}.txt"
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines = [
        f"=== Training Watchdog Report ===",
        f"Time: {now}",
        f"Prefix: {prefix}",
        f"Reason: {reason}",
        f"",
        f"{'Seed':<8} {'Ep':<6} {'Health':<10} {'Ent':<10} {'Critic':<12} {'Last Rwd':<12} {'Best Rwd':<12} {'Comfort%':<10}",
        "-" * 80,
    ]

    for r in results:
        if r:
            lines.append(
                f"seed{r['seed']:<4} {r['episode']:<6} {r['health']:<10} "
                f"{r['ent_coef']:<10.4f} {r['critic_loss']:<12.1f} "
                f"{r['last_reward'] or 0:<12.0f} {r['best_reward'] or 0:<12.0f} "
                f"{r['last_comfort'] or 0:<10.1f}"
            )

    healthy = sum(1 for r in results if r and r["health"] == "HEALTHY")
    diverged = sum(1 for r in results if r and r["health"] == "DIVERGED")
    total = sum(1 for r in results if r)

    lines.extend([
        "",
        f"Summary: {healthy} healthy, {diverged} diverged, {total} total",
    ])

    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


def main():
    parser = argparse.ArgumentParser(description="Training Watchdog")
    parser.add_argument("--prefix", default="e03_nanjing")
    parser.add_argument("--seeds", nargs="+",
                        default=["01", "02", "03", "04", "05", "06",
                                 "07", "08", "09", "10", "11", "12"])
    parser.add_argument("--interval", type=int, default=7200, help="Check interval (seconds)")
    parser.add_argument("--threshold", type=float, default=0.5,
                        help="Fraction of diverged seeds to trigger stop (default: 0.5)")
    args = parser.parse_args()

    print(f"Training Watchdog started")
    print(f"  Prefix: {args.prefix}")
    print(f"  Seeds: {args.seeds}")
    print(f"  Interval: {args.interval}s ({args.interval // 3600}h {(args.interval % 3600) // 60}m)")
    print(f"  Stop threshold: {args.threshold * 100:.0f}% diverged")
    print(f"  Press Ctrl+C to stop\n")

    check_count = 0
    try:
        while True:
            time.sleep(args.interval)
            check_count += 1
            now = datetime.now().strftime("%H:%M:%S")

            results = [check_seed(s, args.prefix) for s in args.seeds]
            valid = [r for r in results if r is not None]

            if not valid:
                print(f"[{now}] Check #{check_count}: no data yet")
                continue

            healthy = sum(1 for r in valid if r["health"] == "HEALTHY")
            unstable = sum(1 for r in valid if r["health"] == "UNSTABLE")
            diverged = sum(1 for r in valid if r["health"] == "DIVERGED")
            finished = sum(1 for r in valid if r["finished"])
            total = len(valid)

            avg_ep = np.mean([r["episode"] for r in valid])

            print(f"[{now}] Check #{check_count}: ep~{avg_ep:.0f}/300 | "
                  f"{healthy} healthy, {unstable} unstable, {diverged} diverged, {finished} finished")

            # Check if all finished
            if finished == total:
                report = write_report(valid, args.prefix, "All seeds completed")
                print(f"  ALL FINISHED. Report: {report}")
                break

            # Check divergence threshold
            if total > 0 and diverged / total >= args.threshold:
                print(f"  *** DIVERGENCE THRESHOLD REACHED: {diverged}/{total} diverged ***")
                print(f"  Killing all training processes...")
                killed = kill_all_training(args.prefix, args.seeds)
                print(f"  Killed {killed} processes")
                report = write_report(valid, args.prefix,
                                       f"Stopped: {diverged}/{total} seeds diverged (threshold={args.threshold})")
                print(f"  Report saved: {report}")
                break

    except KeyboardInterrupt:
        print(f"\nWatchdog stopped manually after {check_count} checks")


if __name__ == "__main__":
    main()
