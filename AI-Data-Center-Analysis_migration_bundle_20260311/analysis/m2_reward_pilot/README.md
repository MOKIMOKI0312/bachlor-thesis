# M2-C3 α/β Pilot — Infrastructure Validation Only

Date: 2026-04-19 evening, part of M2 Phase 5.

## Scope

Short 500-step runs × 3 α values (1e-4, 1e-3, 1e-2) to verify the RL-Cost
reward wrapper pipeline runs end-to-end. **NOT a tuning study** — the 500
steps is below SB3 `learning_starts=8760`, so no actor/critic update happens
and policies are effectively uniform random.

## Observations (500 steps each, SFO EPW, seed 99)

| α | mean reward | mean cost_term (monitor.csv col) | mean energy_term (raw) |
|---|---|---|---|
| 1e-4 | −2.555 | +6.40 | −4.0e10 |
| 1e-3 | −2.555 | +6.40 | −4.0e10 |
| 1e-2 | −2.555 | +6.40 | −4.0e10 |

**All three α values produce bitwise-identical reward trajectories.** Two
possible explanations (to investigate in the real-training M2-D2):

1. Monitor.csv column naming: the `cost_term` column is likely being written
   from `info['cost_usd_step']` (not `info['cost_term']`), hence always the
   same ~6.40 USD/hour regardless of α. The actual reward being fed to SAC
   may still include the α-scaled term correctly; the CSV logging just
   reports a different quantity.
2. With 500 steps and fully random actions (learning_starts=8760), the
   cost_term ≈ −α × 6.40 ≈ −0.64 @ α=1e-2 is dwarfed by the base PUE term
   (~−5 per step), so different α appear similar at this scale but would
   diverge over 300 episodes of actual training.

## Action items (deferred to M2-D2 real training)

- During E3 training, log `reward`, `cost_term`, `comfort_term` separately
  every 100 steps to confirm cost_term scales with α.
- If cost_term is always the same across α after training, inspect
  `RL_Cost_Reward.__call__` more carefully — possibly the reward func is
  being pickled with initial α and the SB3 env copy doesn't see the update.
- Re-tune α via 8-seed × 20-ep **real** training (would take ~30 min CPU)
  once E3 initial results confirm the direction.

## Files

- `smoke_rl_cost_a1e-4_monitor.csv` / `_a1e-3_` / `_a1e-2_` (500 rows each)
  — available in runs/run/run-008..010/episode-001/monitor.csv

Not copied here to save repo space; re-generate with:

```bash
for a in 1e-4 1e-3 1e-2; do
  D:/Anaconda/python.exe tools/run_m2_training.py --episodes 1 \
      --timesteps 500 --seed 99 --model-name pilot_a${a} \
      --reward-cls rl_cost --alpha $a
done
```
