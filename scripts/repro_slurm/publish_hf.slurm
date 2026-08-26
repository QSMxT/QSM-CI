#!/bin/bash
#SBATCH --job-name=qsmci-repro-hf
#SBATCH --account=a_ai_collab
#SBATCH --partition=general
#SBATCH --qos=normal
#SBATCH --time=24:00:00
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --output=/scratch/user/uqaste15/qsmci-repro/slurm-%x-%j.out

# Publish every repro recon volume (results/<id>/recon.nii.gz) to the public HuggingFace dataset
# qsmxt/qsm-ci-volumes, the same repo + mechanism the in-silico track uses. Idempotent: identical
# content is deduped server-side, so re-running after more GPU recons land only uploads the new ones.
# The HF write token is read from a 0600 file staged over stdin (never in argv/env-dumps).
source ~/miniconda3/etc/profile.d/conda.sh && conda activate qsmxt
set -uo pipefail
cd "${SLURM_SUBMIT_DIR:?}"
pip install -q huggingface_hub 2>&1 | tail -1
export HF_TOKEN="$(cat ~/.hf_publish_token)"
export HF_VOLUMES_REPO="qsmxt/qsm-ci-volumes"
echo "publishing $(find results -name recon.nii.gz | wc -l) recon volumes to $HF_VOLUMES_REPO"
python scripts/publish_volumes.py results
echo "publish exit: $?"
