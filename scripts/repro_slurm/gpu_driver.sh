#!/bin/bash
# Queue matrix_gpu.slurm over every acquisition in chunks, never filling the gpu QOS's per-user
# submit limit (MaxSubmitPU, 100 jobs) so other GPU work can still be submitted. Submit this as a small CPU job; the environment (RUNS_PREFIX,
# STREAM_PUBLISH, CAMPAIGN, N_SHARDS) passes through to every chunk.
#   sbatch --export=ALL --time=7-00:00:00 --mem=2G scripts/repro_slurm/gpu_driver.sh <n-acquisitions>
set -uo pipefail
cd "${SLURM_SUBMIT_DIR:?}"
# GPU_START / GPU_END (task indices) resubmit part of the range, e.g. chunks that were refused.
# The gpu QOS allows a user 100 submitted jobs (every array task counts, and other GPU work shares
# them), so chunks are GPU_CHUNK (50) tasks and a chunk is submitted only while this user's gpu-QOS
# jobs plus the chunk stay within GPU_MAX_SUBMITTED (90): at least 10 submit slots stay free for other
# jobs. A refused submission is retried, never skipped.
TOTAL=$(( ${1:?number of acquisitions} * ${N_SHARDS:-4} ))
LAST=$(( ${GPU_END:-$((TOTAL - 1))} ))
CHUNK=${GPU_CHUNK:-50}
MAX=${GPU_MAX_SUBMITTED:-90}
gpu_jobs() { squeue -u "$USER" -h -q gpu -r -o %i 2>/dev/null | wc -l; }
for ((start = ${GPU_START:-0}; start <= LAST; start += CHUNK)); do
  end=$(( start + CHUNK - 1 < LAST ? start + CHUNK - 1 : LAST ))
  n=$(( end - start + 1 ))
  while [ $(( $(gpu_jobs) + n )) -gt "$MAX" ]; do sleep 300; done
  echo "== $(date) chunk $start-$end"
  until jid=$(sbatch --parsable --export=ALL --array=$start-$end%${GPU_THROTTLE:-4} scripts/repro_slurm/matrix_gpu.slurm); do
    echo "   $(date) chunk $start-$end refused; retrying in 10 min"
    sleep 600
  done
  echo "   job $jid"
done
