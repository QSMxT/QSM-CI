#!/bin/bash
#SBATCH --job-name=hf-dedupe-delete
#SBATCH --account=a_ai_collab
#SBATCH --partition=general
#SBATCH --qos=normal
#SBATCH --cpus-per-task=2
#SBATCH --mem=16G
#SBATCH --time=06:00:00
#SBATCH --output=/scratch/user/uqaste15/qsmci-repro/hf-dedupe-delete-%j.out
# STEP 4: remove the per-run ground-truth copies. THIS DELETES.
# Preconditions, all met:
#   - deployed index repointed and MERGED (QSM-CI #241) and verified live: the site returns 0 legacy
#     truth URLs and 1233 shared ones, so nothing served references what this removes;
#   - HPC index repointed in step 3 (job 28237882);
#   - both passes recorded what they rewrote (.dedupe-pending.json, 566 + 1027 paths).
# deletable() still re-checks each file: repointed by a recorded pass, referenced by no supplied
# index, and its bytes already present under truth/ with the same sha256.
set -uo pipefail
cd /scratch/user/uqaste15/qsmci-repro
eval "$(grep '^export HF_QSMXT_KEY=' ~/.bashrc)" 2>/dev/null || true
export HF_TOKEN="${HF_QSMXT_KEY:-}"
export HF_VOLUMES_REPO=qsmxt/qsm-ci-volumes
if [ -z "$HF_TOKEN" ]; then echo "ERROR: HF_TOKEN empty"; exit 1; fi
python3 scripts/dedupe_hf_truth.py --delete-legacy \
    --index results/index.json \
    --index /scratch/user/uqaste15/qsmci-repro/results/_site_index.json
echo "DEDUPE_DELETE_DONE rc=$?"
