#!/bin/bash
#SBATCH --job-name=hf-flat-run
#SBATCH --account=a_ai_collab
#SBATCH --partition=general
#SBATCH --qos=normal
#SBATCH --cpus-per-task=2
#SBATCH --mem=16G
#SBATCH --time=06:00:00
#SBATCH --output=/scratch/user/uqaste15/qsmci-repro/hf-flat-run-%j.out
# REAL RUN: --prune + --prune-flat with deletion enabled.
# Authorised on the evidence of dry run 28228996: 3651 files across 922 retired runs, 922/922 of
# which name a method web/algorithms.json no longer defines (the pre-rename slug generation), with
# the two indexes explaining 63% of the flat root. Deleting does NOT reclaim quota on its own — the
# LFS objects stay in history until scripts/squash_hf_history.py runs.
set -uo pipefail
cd /scratch/user/uqaste15/qsmci-repro
eval "$(grep '^export HF_QSMXT_KEY=' ~/.bashrc)" 2>/dev/null || true
export HF_TOKEN="${HF_QSMXT_KEY:-}"
export HF_VOLUMES_REPO=qsmxt/qsm-ci-volumes
if [ -z "$HF_TOKEN" ]; then echo "ERROR: HF_TOKEN empty"; exit 1; fi
python3 scripts/publish_volumes.py results --prune --prune-flat \
    --index /scratch/user/uqaste15/qsmci-repro/results/_site_index.json
echo "FLAT_RUN_DONE rc=$?"
