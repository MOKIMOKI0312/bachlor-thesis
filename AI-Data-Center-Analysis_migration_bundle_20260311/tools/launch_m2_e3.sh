#!/usr/bin/env bash
# Launch M2 E3 (RL-Cost) training: 8 seed × 300 ep on CAISO SiliconValley.
#
# DO NOT RUN WITHOUT USER APPROVAL — total wall-clock ≈ 2-3 days on 8-core CPU
# with concurrency 4 (recommended to avoid ACE-CORE102700 related crashes).
#
# Recommended batching (because 8 concurrent E+ instances destabilised the
# system in M1; see handoff_2026-04-19.md §8.5):
#   1) Run seeds 1-4 first (this script does that by default)
#   2) After those complete, run `BATCH=2 bash tools/launch_m2_e3.sh` for seeds 5-8
#
# Env setup (must be set in shell OR your .bashrc):
#   export EPLUS_PATH="C:/.../vendor/EnergyPlus-23.1.0-87ed9199d4-Windows-x86_64"
#   cd $(repo root with Eplus-DC-Cooling-TES registered)
#
# Usage:
#   BATCH=1 bash tools/launch_m2_e3.sh   # seeds 1-4 (default)
#   BATCH=2 bash tools/launch_m2_e3.sh   # seeds 5-8
set -euo pipefail

: "${BATCH:=1}"
: "${EPLUS_PATH:?Set EPLUS_PATH to your EnergyPlus 23.1 folder}"
: "${PYTHON_EXE:=D:/Anaconda/python.exe}"

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="$REPO;$EPLUS_PATH"
export KMP_DUPLICATE_LIB_OK=TRUE  # OpenMP duplicate guard (see run_m2_training.py)

case "$BATCH" in
  1) SEEDS=(1 2 3 4) ;;
  2) SEEDS=(5 6 7 8) ;;
  all) SEEDS=(1 2 3 4 5 6 7 8) ;;
  *) echo "BATCH must be 1 / 2 / all"; exit 2 ;;
esac

echo "Launching M2-E3 (RL-Cost) for seeds: ${SEEDS[*]}"
echo "  repo=$REPO"
echo "  python=$PYTHON_EXE"
echo ""

for seed in "${SEEDS[@]}"; do
  JOB="m2-e3-seed${seed}"
  echo "==> Launching $JOB ..."
  "$PYTHON_EXE" "$REPO/tools/launch_training_background.py" \
    --repo "$REPO" \
    --episodes 300 \
    --seed "$seed" \
    --device cpu \
    --model-name "e3_rl_cost_seed${seed}" \
    --checkpoint-episodes 10 \
    --job-name "$JOB" \
    --python-exe "$PYTHON_EXE" \
    --algo dsac_t \
    --training-script tools/run_m2_training.py \
    --wandb-group M2-E3 \
    -- \
    --reward-cls rl_cost \
    --alpha 1e-3 --beta 1.0
  sleep 30   # stagger to avoid IO spike
done

echo ""
echo "Launched ${#SEEDS[@]} jobs. Monitor with:"
echo "  ls training_jobs/m2-e3-seed*/status.json"
echo ""
echo "Stop all with:  tools/stop_m2_training.sh"
