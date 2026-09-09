#!/bin/bash
#SBATCH --job-name=hf-prune-dry
#SBATCH --time=03:00:00
#SBATCH --mem=16G
#SBATCH --cpus-per-task=2
#SBATCH --partition=general
#SBATCH --account=a_ai_collab
#SBATCH --output=/scratch/user/uqaste15/qsmci-repro/hf-prune-dry-%j.out
# Report what pruning WOULD delete from the HF volumes repo. Deletes NOTHING.
#
# ALWAYS run this and read the output before a real --prune. In 2026-09 a dry run against the live
# repo reported 623 orphans of which 621 were the shared magnitude/total-field/local-field volumes
# the viewer needs — they are published by publish_intermediates.slurm, so a per-run publish does
# not produce them, and nothing in index.json names them. publish_volumes.py now scopes prune to
# recognised per-run artifacts so that cannot recur, but the dry run is what caught it.
set -euo pipefail
cd /scratch/user/uqaste15/qsmci-repro
eval "$(grep '^export HF_QSMXT_KEY=' ~/.bashrc)" 2>/dev/null || true
export HF_TOKEN="${HF_QSMXT_KEY:-}"
export HF_VOLUMES_REPO=qsmxt/qsm-ci-volumes
if [ -z "$HF_TOKEN" ]; then echo "ERROR: HF_TOKEN empty"; exit 1; fi
python scripts/publish_volumes.py results --prune --prune-dry-run
echo "PRUNE_DRY_DONE rc=$?"
