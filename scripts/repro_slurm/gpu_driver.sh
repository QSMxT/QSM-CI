#!/bin/bash
# Queue matrix_gpu.slurm over every acquisition in chunks of 100 array tasks, each chunk waiting for
# the one before: the gpu QOS allows a user 100 submitted jobs (MaxSubmitPU), so the whole array
# can't be queued at once. Submit this as a small CPU job; the environment (RUNS_PREFIX,
# STREAM_PUBLISH, CAMPAIGN, N_SHARDS) passes through to every chunk.
#   sbatch --export=ALL --time=7-00:00:00 --mem=2G scripts/repro_slurm/gpu_driver.sh <n-acquisitions>
set -uo pipefail
cd "${SLURM_SUBMIT_DIR:?}"
# GPU_START / GPU_END (task indices) resubmit part of the range, e.g. chunks that were refused.
# A refused submission (the gpu QOS's per-user submit limit counts other GPU jobs too) is retried
# every 10 minutes instead of skipped: `sbatch --wait` exits non-zero both when the submission is
# refused and when a task fails, so the refusal is recognised by the missing job id.
TOTAL=$(( ${1:?number of acquisitions} * ${N_SHARDS:-4} ))
LAST=$(( ${GPU_END:-$((TOTAL - 1))} ))
for ((start = ${GPU_START:-0}; start <= LAST; start += 100)); do
  end=$(( start + 99 < LAST ? start + 99 : LAST ))
  echo "== $(date) chunk $start-$end"
  until jid=$(sbatch --parsable --export=ALL --array=$start-$end%${GPU_THROTTLE:-4} scripts/repro_slurm/matrix_gpu.slurm); do
    echo "   $(date) chunk $start-$end refused; retrying in 10 min"
    sleep 600
  done
  while squeue -j "$jid" -h 2>/dev/null | grep -q .; do sleep 300; done
  echo "   $(date) chunk $start-$end (job $jid) done: $(sacct -j "$jid" -n -X -o State | sort | uniq -c | tr -s ' \n' ' ')"
done
