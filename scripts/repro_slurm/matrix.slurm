#!/bin/bash
#SBATCH --job-name=qsmci-repro-matrix
#SBATCH --account=a_ai_collab
#SBATCH --partition=general
#SBATCH --qos=normal
#SBATCH --time=24:00:00
#SBATCH --cpus-per-task=16
# 64G, not the 300G this used to reserve: across 184 completed tasks of this exact array (same
# --exclude, same QSM_CI_JOBS) sacct put median MaxRSS at 21.7G and the PEAK at 31.4G, so 300G
# over-reserved by ~10x. 64G keeps 2x headroom over that peak. If you ever drop the inr-qsm/modip
# exclusion below, raise this again — inr-qsm's full-volume SIREN is what made the old number look
# necessary (see matrix_gpu.slurm, which keeps 256G for exactly that reason).
#SBATCH --mem=64G
# %40, not %12: the throttle was the only thing limiting concurrency here. Pending tasks sat on
# reason=JobArrayTaskLimit while the partition had thousands of idle CPUs, and 40 concurrent tasks
# schedule without trouble. At a ~1.5h median task this is ~3-4h for the 92-task array instead of
# ~12-14h.
#SBATCH --array=0-91%40
#SBATCH --output=slurm-%x-%A_%a.out

# Full composed matrix over the 23 harmonization acquisitions, 4 shards each: array index
# = 4*acq + shard. Each task runs one shard of one acquisition's (field-mapping x bfr x dipole
# + spans) matrix from raw phase, collecting (not scoring) every produced chimap.
source ~/miniconda3/etc/profile.d/conda.sh && conda activate qsmxt   # before set -u (conda gotcha)
set -uo pipefail
cd "${SLURM_SUBMIT_DIR:?}"
export APPTAINER_CACHEDIR=/scratch/user/uqaste15/apptainer_cache
export QSM_CI_JOBS=4

N_SHARDS=4
mapfile -t ACQS < <(python -c "
import json
reg = json.load(open('scripts/datasets.json'))
print('\n'.join(sorted(k for k, v in reg.items() if v.get('track') == 'repro')))")
ACQ=${ACQS[$((SLURM_ARRAY_TASK_ID / N_SHARDS))]}
SHARD=$((SLURM_ARRAY_TASK_ID % N_SHARDS))

echo "== acquisition $ACQ shard $SHARD/$N_SHARDS"
# inr-qsm (per-volume SIREN fit) and modip (per-subject optimisation) are CPU-infeasible at this
# scale (~400 slow inversions each across the matrix) — they get a dedicated GPU/big-mem campaign
# later, via matrix_gpu.slurm.
python scripts/pipeline.py \
    --phantom "$ACQ" --track repro --mode composed --runner apptainer \
    --shard "$SHARD/$N_SHARDS" \
    --exclude inr-qsm,modip \
    --work ".work-repro-$ACQ-$SHARD" \
    --runs-out "results/runs-repro-$ACQ-s$SHARD.json"
rm -rf ".work-repro-$ACQ-$SHARD"
