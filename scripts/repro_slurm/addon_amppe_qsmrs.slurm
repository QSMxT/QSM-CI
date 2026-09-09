#!/bin/bash
#SBATCH --job-name=qsmci-amppe-qsmrs
#SBATCH --account=a_ai_collab
#SBATCH --partition=general
#SBATCH --qos=normal
#SBATCH --time=08:00:00
#SBATCH --cpus-per-task=16
#SBATCH --mem=300G
#SBATCH --array=0-22%12
#SBATCH --output=slurm-%x-%A_%a.out

# Addon pass: compute ONLY the amp-pe-qsmrs (Rust/QSMxT) dipole pipelines on the SAME (1-eroded) masks
# the eroded matrix used, so the new AMP-PE slots consistently alongside the existing results. Uses
# --focus amp-pe-qsmrs => the dipole stage is pinned to amp-pe-qsmrs while every field-mapping x bfr
# combo still runs (matching the coverage the ci_skip'd MATLAB `amp-pe` had). Run this AFTER the main
# eroded matrix (27871761) finishes so it doesn't perturb that run. One shard per acq (fast: one dipole).
source ~/miniconda3/etc/profile.d/conda.sh && conda activate qsmxt   # before set -u (conda gotcha)
set -uo pipefail
cd "${SLURM_SUBMIT_DIR:?}"
export APPTAINER_CACHEDIR=/scratch/user/uqaste15/apptainer_cache
export APPTAINER_TMPDIR=/scratch/user/uqaste15/apptainer_tmp
export PROOT_NO_SECCOMP=1
export QSMCI_SANDBOX_DIR=/scratch/project_mnt/S0169/qsmci_sif
export QSM_CI_JOBS=4

mapfile -t ACQS < <(python -c "
import json
reg = json.load(open('scripts/datasets.json'))
print('\n'.join(sorted(k for k, v in reg.items() if v.get('track') == 'repro')))")
ACQ=${ACQS[$SLURM_ARRAY_TASK_ID]}

echo "== [amppe-qsmrs] acquisition $ACQ (focus=amp-pe-qsmrs, QSMCI_SANDBOX_DIR=$QSMCI_SANDBOX_DIR)"
python scripts/pipeline.py \
    --phantom "$ACQ" --track repro --mode composed --runner apptainer \
    --focus amp-pe-qsmrs \
    --work ".work-amppe-$ACQ" \
    --runs-out "results/runs-repro-$ACQ-amppe.json"
rm -rf ".work-amppe-$ACQ"
