#!/bin/bash
#SBATCH --job-name=hf-dedupe-hpc
#SBATCH --account=a_ai_collab
#SBATCH --partition=general
#SBATCH --qos=normal
#SBATCH --cpus-per-task=2
#SBATCH --mem=16G
#SBATCH --time=06:00:00
#SBATCH --output=/scratch/user/uqaste15/qsmci-repro/hf-dedupe-hpc-%j.out
# STEP 3: repoint the HPC index (results/index.json), the one that still protects 1027 legacy truth
# files. The DEPLOYED index is passed second, as protection only — it was rewritten in step 2 and
# merged as QSM-CI #241, so it no longer references any legacy path and protects nothing here.
# Deletes NOTHING; --delete-legacy is step 4.
set -uo pipefail
cd /scratch/user/uqaste15/qsmci-repro
eval "$(grep '^export HF_QSMXT_KEY=' ~/.bashrc)" 2>/dev/null || true
export HF_TOKEN="${HF_QSMXT_KEY:-}"
export HF_VOLUMES_REPO=qsmxt/qsm-ci-volumes
if [ -z "$HF_TOKEN" ]; then echo "ERROR: HF_TOKEN empty"; exit 1; fi
cp results/index.json results/index.json.pre-dedupe.bak
python3 scripts/dedupe_hf_truth.py \
    --index results/index.json \
    --index /scratch/user/uqaste15/qsmci-repro/results/_site_index.json
echo "DEDUPE_HPC_DONE rc=$?"
