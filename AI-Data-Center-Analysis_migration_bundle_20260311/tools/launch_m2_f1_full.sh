#!/usr/bin/env bash
# Launch M2-F1 full training: 6 seeds × 300 ep on the F1 (TES SOC random) branch.
#
# Based on the successful F1 pilot 2 seed × 30 ep (§7.11 of progress doc):
# - critic omega=2.6-4.3 (baseline 14, 5× 更稳)
# - reward -1.11 (baseline -2.15, 改善 47%)
# - TES 年周期 123-320 (baseline 1, target 30+, 暴击 10×)
# - seed2 ep13 TOU 已单调 (trough<normal<peak)
#
# DO NOT RUN WITHOUT USER APPROVAL —
# - Wall-clock: ~6-8 hours/seed on CPU, ~1.5-2 days 6 seed parallel on 8-core CPU
# - Storage: ~3-4 GB/seed = 20+ GB total in runs/
#
# Env prerequisites:
#   export EPLUS_PATH="$(pwd)/vendor/EnergyPlus-23.1.0-87ed9199d4-Windows-x86_64"
#   export PYTHONPATH="$(pwd):$EPLUS_PATH"
#   export KMP_DUPLICATE_LIB_OK=TRUE
#
# Usage:
#   cd <fix-tes-soc-random worktree>
#   BATCH=1 bash tools/launch_m2_f1_full.sh   # seeds 1-3 (default)
#   BATCH=2 bash tools/launch_m2_f1_full.sh   # seeds 4-6
#   BATCH=all bash tools/launch_m2_f1_full.sh # all 6 (high CPU contention)

set -euo pipefail

: "${BATCH:=1}"
: "${EPLUS_PATH:?Set EPLUS_PATH to your EnergyPlus 23.1 folder}"
: "${PYTHON_EXE:=D:/Anaconda/python.exe}"
: "${EPISODES:=300}"
: "${ALPHA:=5e-4}"
: "${BETA:=1.0}"

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="$REPO;$EPLUS_PATH"
export KMP_DUPLICATE_LIB_OK=TRUE

case "$BATCH" in
  1) SEEDS=(1 2 3) ;;
  2) SEEDS=(4 5 6) ;;
  all) SEEDS=(1 2 3 4 5 6) ;;
  *) echo "BATCH must be 1 / 2 / all"; exit 2 ;;
esac

echo "Launching M2-F1 full training for seeds: ${SEEDS[*]}"
echo "  repo=$REPO"
echo "  python=$PYTHON_EXE"
echo "  episodes=$EPISODES  alpha=$ALPHA  beta=$BETA"
echo "  F1: TES initial tank temperature ~ U(6, 12) °C per episode"
echo ""

for seed in "${SEEDS[@]}"; do
  JOB="m2-f1-full-seed${seed}"
  echo "==> Launching $JOB ..."
  "$PYTHON_EXE" "$REPO/tools/launch_training_background.py" \
    --repo "$REPO" \
    --episodes "$EPISODES" \
    --seed "$seed" \
    --device cpu \
    --model-name "m2_f1_full_seed${seed}" \
    --checkpoint-episodes 20 \
    --job-name "$JOB" \
    --python-exe "$PYTHON_EXE" \
    --algo dsac_t \
    --training-script tools/run_m2_training.py \
    --wandb-group M2-F1-full \
    -- \
    --reward-cls rl_cost \
    --alpha "$ALPHA" --beta "$BETA"
  sleep 30
done

echo ""
echo "Launched ${#SEEDS[@]} jobs. Monitor with:"
echo "  ls training_jobs/m2-f1-full-seed*/status.json"
echo ""
echo "Success criteria after 300 ep completion:"
echo "  - critic omega < 100, sigma < 10 (baseline 14, 5; pilot 2.6-4.3, 1.5-2.1)"
echo "  - TES cycles >> 30 per year (baseline 1; pilot 120-320)"
echo "  - TOU ordering: trough_TES < normal < peak (pilot: seed2 already, seed1 near)"
echo "  - SOC 24h daily cycle amplitude > 0.1 (pilot still flat 0.03, 300 ep 应发展)"
echo "  - reward < -1.15 (baseline -2.15, pilot -1.11)"
echo "  - comfort_viol% < 5% (baseline 8%, pilot 2-5%)"
