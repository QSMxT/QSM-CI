#!/bin/bash
#SBATCH --job-name=hf-dedupe-dry
#SBATCH --account=a_ai_collab
#SBATCH --partition=general
#SBATCH --qos=normal
#SBATCH --cpus-per-task=2
#SBATCH --mem=16G
#SBATCH --time=04:00:00
#SBATCH --output=/scratch/user/uqaste15/qsmci-repro/hf-dedupe-dry-%j.out
# Plan the shared-ground-truth collapse. Deletes and uploads NOTHING (--dry-run).
# Both indexes are passed: the deployed one (rewritten first) and the HPC's (protection only).
# Listing ~57k files with LFS metadata takes a while, which is why this is a batch job and not
# something to run on the login node.
set -uo pipefail
cd /scratch/user/uqaste15/qsmci-repro
eval "$(grep '^export HF_QSMXT_KEY=' ~/.bashrc)" 2>/dev/null || true
export HF_TOKEN="${HF_QSMXT_KEY:-}"
export HF_VOLUMES_REPO=qsmxt/qsm-ci-volumes
if [ -z "$HF_TOKEN" ]; then echo "ERROR: HF_TOKEN empty"; exit 1; fi
python3 scripts/dedupe_hf_truth.py --dry-run \
    --index /scratch/user/uqaste15/qsmci-repro/results/_site_index.json --index results/index.json
echo "DEDUPE_DRY_DONE rc=$?"
