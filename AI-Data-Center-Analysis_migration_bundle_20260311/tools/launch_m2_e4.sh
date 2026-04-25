#!/usr/bin/env bash
# Launch M2 E4 (RL-Green) training: 8 seed × 300 ep on CAISO SiliconValley.
#
# DO NOT RUN WITHOUT USER APPROVAL — total wall-clock ≈ 2-3 days on 8-core CPU.
# Run AFTER E3 (RL-Cost) finishes to avoid 16 concurrent E+ instances
# overwhelming the system.
#
# See launch_m2_e3.sh for env setup requirements.
#
# Usage:
#   BATCH=1 bash tools/launch_m2_e4.sh   # seeds 1-4 (default)
#   BATCH=2 bash tools/launch_m2_e4.sh   # seeds 5-8
set -euo pipefail

: "${BATCH:=1}"
: "${EPLUS_PATH:?Set EPLUS_PATH to your EnergyPlus 23.1 folder}"
: "${PYTHON_EXE:=D:/Anaconda/python.exe}"

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="$REPO;$EPLUS_PATH"
export KMP_DUPLICATE_LIB_OK=TRUE

case "$BATCH" in
  1) SEEDS=(1 2 3 4) ;;
  2) SEEDS=(5 6 7 8) ;;
  all) SEEDS=(1 2 3 4 5 6 7 8) ;;
  *) echo "BATCH must be 1 / 2 / all"; exit 2 ;;
esac

echo "Launching M2-E4 (RL-Green) for seeds: ${SEEDS[*]}"
echo "  repo=$REPO"
echo "  python=$PYTHON_EXE"
echo ""

for seed in "${SEEDS[@]}"; do
  JOB="m2-e4-seed${seed}"
  echo "==> Launching $JOB ..."
  "$PYTHON_EXE" "$REPO/tools/launch_training_background.py" \
    --repo "$REPO" \
    --episodes 300 \
    --seed "$seed" \
    --device cpu \
    --model-name "e4_rl_green_seed${seed}" \
    --checkpoint-episodes 10 \
    --job-name "$JOB" \
    --python-exe "$PYTHON_EXE" \
    --algo dsac_t \
    --training-script tools/run_m2_training.py \
    --wandb-group M2-E4 \
    -- \
    --reward-cls rl_green \
    --alpha 1e-3 --beta 1.0 \
    --c-pv 0.0 --pv-threshold-kw 100.0
  sleep 30
done

echo ""
echo "Launched ${#SEEDS[@]} jobs. Monitor with:"
echo "  ls training_jobs/m2-e4-seed*/status.json"
