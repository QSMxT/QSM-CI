#!/bin/bash
#SBATCH --job-name=hf-flat-dry
#SBATCH --account=a_ai_collab
#SBATCH --partition=general
#SBATCH --qos=normal
#SBATCH --cpus-per-task=2
#SBATCH --mem=16G
#SBATCH --time=06:00:00
#SBATCH --output=/scratch/user/uqaste15/qsmci-repro/hf-flat-dry-%j.out
# Report what --prune and --prune-flat WOULD delete. Deletes nothing.
# Note this still UPLOADS: --prune-dry-run suppresses deletion only, so the publish runs in full
# (~1.9 GB, ~20 min) before the prune report. Definitely not login-node work.
set -uo pipefail
cd /scratch/user/uqaste15/qsmci-repro
eval "$(grep '^export HF_QSMXT_KEY=' ~/.bashrc)" 2>/dev/null || true
export HF_TOKEN="${HF_QSMXT_KEY:-}"
export HF_VOLUMES_REPO=qsmxt/qsm-ci-volumes
if [ -z "$HF_TOKEN" ]; then echo "ERROR: HF_TOKEN empty"; exit 1; fi
python3 scripts/publish_volumes.py results --prune --prune-dry-run --prune-flat \
    --index /scratch/user/uqaste15/qsmci-repro/results/_site_index.json
echo "FLAT_DRY_DONE rc=$?"
