#!/bin/bash
#SBATCH --job-name=qsmci-repro-matrix
#SBATCH --account=a_ai_collab
#SBATCH --partition=general
#SBATCH --qos=normal
#SBATCH --time=24:00:00
#SBATCH --cpus-per-task=16
#SBATCH --mem=300G
#SBATCH --array=0-91%12
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
# later, like scripts/score_dl.slurm did for the sim scoring.
python scripts/pipeline.py \
    --phantom "$ACQ" --track repro --mode composed --runner apptainer \
    --shard "$SHARD/$N_SHARDS" \
    --exclude inr-qsm,modip \
    --work ".work-repro-$ACQ-$SHARD" \
    --runs-out "results/runs-repro-$ACQ-s$SHARD.json"
rm -rf ".work-repro-$ACQ-$SHARD"
