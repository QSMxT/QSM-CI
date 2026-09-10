#!/bin/bash
#SBATCH --job-name=hf-dedupe-repoint
#SBATCH --account=a_ai_collab
#SBATCH --partition=general
#SBATCH --qos=normal
#SBATCH --cpus-per-task=2
#SBATCH --mem=16G
#SBATCH --time=06:00:00
#SBATCH --output=/scratch/user/uqaste15/qsmci-repro/hf-dedupe-repoint-%j.out
# STEP 2 of the ground-truth collapse: upload the shared truth files and repoint the DEPLOYED index
# (results/_site_index.json — a copy of the committed results/index.json). Deletes NOTHING; the
# per-run copies go only in step 4, after this rewritten index is committed and deployed.
# Per dry run 28228995: creates 12 shared files, the largest serving 305 runs from one copy.
# The HPC index is passed as protection only and is NOT rewritten by this pass.
set -uo pipefail
cd /scratch/user/uqaste15/qsmci-repro
eval "$(grep '^export HF_QSMXT_KEY=' ~/.bashrc)" 2>/dev/null || true
export HF_TOKEN="${HF_QSMXT_KEY:-}"
export HF_VOLUMES_REPO=qsmxt/qsm-ci-volumes
if [ -z "$HF_TOKEN" ]; then echo "ERROR: HF_TOKEN empty"; exit 1; fi
cp results/_site_index.json results/_site_index.json.bak    # so the diff has a baseline
python3 scripts/dedupe_hf_truth.py \
    --index /scratch/user/uqaste15/qsmci-repro/results/_site_index.json \
    --index results/index.json
echo "DEDUPE_REPOINT_DONE rc=$?"
