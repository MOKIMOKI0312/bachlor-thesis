"""
Verify DSAC-T σ-divergence diagnosis on Pendulum-v1 (no EnergyPlus needed).

Runs three configurations and records σ_mean / clip_b / critic_loss / actor_loss
every 500 training steps into JSONL:
  1) baseline   : current code, no fix
  2) sigma_clamp: +sigma_max=30 (FIX-1 only)
  3) full_fix   : +sigma_max=30 +grad_clip=10 +beta_b=0.02 (FIX-1+2+3)

Expected outcome (if diagnosis is correct):
  - baseline σ escalates past any reasonable bound (100+, possibly 1000+)
  - sigma_clamp σ saturates at 30 but may still have actor_loss drift
  - full_fix σ stays within bounds and losses stay well-behaved

Runtime: ~5-8 min total on CPU.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
import torch as th
import gymnasium as gym

from tools.dsac_t import DSAC_T


class MetricsProbeCallback:
    """Polls the DSAC-T internal state every N steps and writes to JSONL.

    We don't use SB3's BaseCallback because we want to probe after each train()
    call, which is cleanly exposed via the logger.
    """

    def __init__(self, model: DSAC_T, out_path: Path, poll_every_steps: int = 500):
        self.model = model
        self.out_path = out_path
        self.poll_every_steps = poll_every_steps
        self._last_polled_updates = -1
        self.records = []

    def poll(self):
        n_upd = self.model._n_updates
        if n_upd == self._last_polled_updates:
            return
        if n_upd % self.poll_every_steps != 0 and n_upd < self.poll_every_steps:
            return
        # snapshot logger values
        logged = {}
        name_to_value = getattr(self.model.logger, "name_to_value", {})
        for k in ("train/sigma_mean", "train/clip_b", "train/omega",
                  "train/actor_loss", "train/critic_loss", "train/ent_coef"):
            if k in name_to_value:
                logged[k] = float(name_to_value[k])
        if not logged:
            return
        self._last_polled_updates = n_upd
        self.records.append({
            "num_timesteps": int(self.model.num_timesteps),
            "n_updates": int(n_upd),
            "sigma_mean": logged.get("train/sigma_mean"),
            "clip_b": logged.get("train/clip_b"),
            "omega": logged.get("train/omega"),
            "actor_loss": logged.get("train/actor_loss"),
            "critic_loss": logged.get("train/critic_loss"),
            "ent_coef": logged.get("train/ent_coef"),
        })


def run_config(tag: str, total_timesteps: int, seed: int,
               sigma_max=None, grad_clip_norm=None, beta_b=None,
               out_dir: Path = Path(".")):
    print(f"\n=== {tag} (seed={seed}, total={total_timesteps}) ===")
    print(f"    sigma_max={sigma_max}, grad_clip_norm={grad_clip_norm}, beta_b={beta_b}")

    env = gym.make("Pendulum-v1")
    env.action_space.seed(seed)

    kw = dict(
        policy="MlpPolicy",
        env=env,
        batch_size=256,
        learning_rate=3e-4,
        learning_starts=1000,
        gamma=0.99,
        train_freq=1,
        gradient_steps=1,
        seed=seed,
        device="cpu",
        verbose=0,
        policy_kwargs=dict(net_arch=[256, 256]),
    )
    if sigma_max is not None:
        kw["sigma_max"] = sigma_max
    if grad_clip_norm is not None:
        kw["grad_clip_norm"] = grad_clip_norm
    if beta_b is not None:
        kw["beta_b"] = beta_b

    np.random.seed(seed)
    th.manual_seed(seed)

    model = DSAC_T(**kw)

    out_path = out_dir / f"probe_{tag}.jsonl"
    probe = MetricsProbeCallback(model, out_path, poll_every_steps=500)

    # Hook into train() via monkey-patch so we poll after each train call.
    _orig_train = model.train

    def _train_and_poll(*a, **kw):
        _orig_train(*a, **kw)
        probe.poll()

    model.train = _train_and_poll

    t0 = time.time()
    try:
        model.learn(total_timesteps=total_timesteps, log_interval=10)
        status = "ok"
        err = None
    except Exception as e:  # noqa: BLE001
        status = "crashed"
        err = f"{type(e).__name__}: {e}"
        print(f"    !! crashed: {err}")
    elapsed = time.time() - t0

    # Save records
    with open(out_path, "w") as f:
        for r in probe.records:
            f.write(json.dumps(r) + "\n")

    print(f"    wrote {len(probe.records)} probe points to {out_path}")
    print(f"    elapsed: {elapsed:.1f}s  status: {status}")
    if probe.records:
        last = probe.records[-1]
        print(f"    final: n_upd={last['n_updates']} σ={last['sigma_mean']:.2f}  "
              f"clip_b={last['clip_b']:.2f}  actor_loss={last['actor_loss']:.2f}  "
              f"critic_loss={last['critic_loss']:.3f}")
    env.close()
    return {"tag": tag, "status": status, "error": err,
            "elapsed_s": elapsed, "records": probe.records}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--timesteps", type=int, default=20000)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--out-dir", type=Path, default=Path("tmp/dsac_verify"))
    parser.add_argument("--skip", nargs="*", default=[], help="configs to skip: baseline sigma_clamp full_fix")
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)

    results = {}
    if "baseline" not in args.skip:
        results["baseline"] = run_config(
            "baseline", args.timesteps, args.seed, out_dir=args.out_dir
        )
    if "sigma_clamp" not in args.skip:
        results["sigma_clamp"] = run_config(
            "sigma_clamp", args.timesteps, args.seed, sigma_max=30.0, out_dir=args.out_dir
        )
    if "full_fix" not in args.skip:
        results["full_fix"] = run_config(
            "full_fix", args.timesteps, args.seed,
            sigma_max=30.0, grad_clip_norm=10.0, beta_b=0.02, out_dir=args.out_dir
        )

    summary_path = args.out_dir / "summary.json"
    summary = {}
    for tag, r in results.items():
        summary[tag] = {
            "status": r["status"],
            "error": r["error"],
            "elapsed_s": r["elapsed_s"],
            "n_records": len(r["records"]),
            "final": r["records"][-1] if r["records"] else None,
        }
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)

    print("\n=== SUMMARY ===")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
