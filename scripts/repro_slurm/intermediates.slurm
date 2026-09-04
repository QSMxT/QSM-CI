#!/bin/bash
#SBATCH --job-name=qsmci-repro-inter
#SBATCH --account=a_ai_collab
#SBATCH --partition=general
#SBATCH --qos=normal
#SBATCH --time=8:00:00
#SBATCH --cpus-per-task=16
#SBATCH --mem=200G
#SBATCH --array=0-22%8
#SBATCH --output=slurm-%x-%A_%a.out

# Regenerate the harmonization track's INTERMEDIATE maps for the submission viewer: the field-mapping
# stage's total field and the background-removal stage's local field.
#
# These are per-COLUMN, not per-pipeline — one total field per field-mapping method, one local field
# per (field-mapping, bfr) pair — so `--columns-only` stops after the two upstream stages and never
# runs the dipole stage that multiplies 26 runs out into 660 pipelines. One array task per
# acquisition, no sharding: 26 runs each is a short job.
#
# The matrix runs deleted their work dirs, so nothing here is recoverable from the earlier passes;
# this recomputes the columns with the same submissions, inputs and masks, which is what the
# published recons were built on.
source ~/miniconda3/etc/profile.d/conda.sh && conda activate qsmxt   # before set -u (conda gotcha)
set -uo pipefail
cd "${SLURM_SUBMIT_DIR:?}"
export APPTAINER_CACHEDIR=/scratch/user/uqaste15/apptainer_cache
export APPTAINER_TMPDIR=/scratch/user/uqaste15/apptainer_tmp
export PROOT_NO_SECCOMP=1
export QSMCI_SANDBOX_DIR=/scratch/project_mnt/S0169/qsmci_sif   # runner execs the prebuilt .sif here
export QSM_CI_JOBS=4

mapfile -t ACQS < <(python -c "
import json
reg = json.load(open('scripts/datasets.json'))
print('\n'.join(sorted(k for k, v in reg.items() if v.get('track') == 'repro')))")
ACQ=${ACQS[$SLURM_ARRAY_TASK_ID]}

echo "== [intermediates] acquisition $ACQ"
python scripts/pipeline.py \
    --phantom "$ACQ" --track repro --mode composed --runner apptainer \
    --columns-only --emit-intermediates \
    --exclude inr-qsm,modip \
    --work ".work-repro-inter-$ACQ"
rm -rf ".work-repro-inter-$ACQ"
ls -la "results/_intermediates/$ACQ" 2>/dev/null | tail -30
