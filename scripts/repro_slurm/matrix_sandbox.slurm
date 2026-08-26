#!/bin/bash
#SBATCH --job-name=qsmci-repro-matrix-sb
#SBATCH --account=a_ai_collab
#SBATCH --partition=general
#SBATCH --qos=normal
#SBATCH --time=24:00:00
#SBATCH --cpus-per-task=16
#SBATCH --mem=300G
#SBATCH --array=0-91%12
#SBATCH --output=slurm-%x-%A_%a.out

# Full-coverage re-run of the composed matrix with the local-sandbox override enabled
# (QSMCI_SANDBOX_DIR). The methods whose images couldn't be built as .sif on Bunya
# (build_sandboxes.slurm) now exec their prebuilt sandbox directories, so the ~18 DL/MATLAB/span
# methods that 100%-DNF'd in the first pass now run. Regenerates every run id; the merge upserts,
# so this supersedes the partial first pass. inr-qsm/modip stay excluded (CPU-infeasible at this
# scale — a separate GPU concern, not a container-conversion one).
source ~/miniconda3/etc/profile.d/conda.sh && conda activate qsmxt   # before set -u (conda gotcha)
set -uo pipefail
cd "${SLURM_SUBMIT_DIR:?}"
export APPTAINER_CACHEDIR=/scratch/user/uqaste15/apptainer_cache
export APPTAINER_TMPDIR=/scratch/user/uqaste15/apptainer_tmp
export PROOT_NO_SECCOMP=1
export QSMCI_SANDBOX_DIR=/scratch/project_mnt/S0169/qsmci_sif   # runner execs the prebuilt .sif here
export QSM_CI_JOBS=4

N_SHARDS=4
mapfile -t ACQS < <(python -c "
import json
reg = json.load(open('scripts/datasets.json'))
print('\n'.join(sorted(k for k, v in reg.items() if v.get('track') == 'repro')))")
ACQ=${ACQS[$((SLURM_ARRAY_TASK_ID / N_SHARDS))]}
SHARD=$((SLURM_ARRAY_TASK_ID % N_SHARDS))

echo "== [sandbox] acquisition $ACQ shard $SHARD/$N_SHARDS (QSMCI_SANDBOX_DIR=$QSMCI_SANDBOX_DIR)"
python scripts/pipeline.py \
    --phantom "$ACQ" --track repro --mode composed --runner apptainer \
    --shard "$SHARD/$N_SHARDS" \
    --exclude inr-qsm,modip \
    --work ".work-repro-sb-$ACQ-$SHARD" \
    --runs-out "results/runs-repro-$ACQ-s$SHARD.json"
rm -rf ".work-repro-sb-$ACQ-$SHARD"
