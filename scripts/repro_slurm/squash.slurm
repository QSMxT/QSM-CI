#!/bin/bash
#SBATCH --job-name=hf-squash
#SBATCH --account=a_ai_collab
#SBATCH --partition=general
#SBATCH --qos=normal
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=02:00:00
#SBATCH --output=/scratch/user/uqaste15/qsmci-repro/hf-squash-%j.out
# STEP 5: collapse the dataset repo's git history to one commit, releasing the LFS objects for
# everything deleted today (3651 retired-run volumes + 1193 per-run truth copies). Destructive to
# HISTORY only — HEAD content is untouched, which is why it cannot break the site. Quota on the Hub
# reflects it within ~36h, not immediately.
# Safe to run now: every truth URL the live site references was verified reachable after the
# deletions (17/17, zero broken).
set -uo pipefail
cd /scratch/user/uqaste15/qsmci-repro
eval "$(grep '^export HF_QSMXT_KEY=' ~/.bashrc)" 2>/dev/null || true
export HF_TOKEN="${HF_QSMXT_KEY:-}"
export HF_VOLUMES_REPO=qsmxt/qsm-ci-volumes
if [ -z "$HF_TOKEN" ]; then echo "ERROR: HF_TOKEN empty"; exit 1; fi
python3 scripts/squash_hf_history.py
echo "SQUASH_DONE rc=$?"
