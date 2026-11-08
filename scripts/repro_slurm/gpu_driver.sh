#!/bin/bash
# Queue matrix_gpu.slurm over every acquisition in chunks of 100 array tasks, each chunk waiting for
# the one before: the gpu QOS allows a user 100 submitted jobs (MaxSubmitPU), so the whole array
# can't be queued at once. Submit this as a small CPU job; the environment (RUNS_PREFIX,
# STREAM_PUBLISH, CAMPAIGN, N_SHARDS) passes through to every chunk.
#   sbatch --export=ALL --time=7-00:00:00 --mem=2G scripts/repro_slurm/gpu_driver.sh <n-acquisitions>
set -uo pipefail
cd "${SLURM_SUBMIT_DIR:?}"
TOTAL=$(( ${1:?number of acquisitions} * ${N_SHARDS:-4} ))
for ((start = 0; start < TOTAL; start += 100)); do
  end=$(( start + 99 < TOTAL - 1 ? start + 99 : TOTAL - 1 ))
  echo "== $(date) chunk $start-$end"
  sbatch --wait --export=ALL --array=$start-$end%4 scripts/repro_slurm/matrix_gpu.slurm
  echo "   $(date) chunk $start-$end exit $?"
done
