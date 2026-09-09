#!/bin/bash
#SBATCH --job-name=repro-hf-upload
#SBATCH --account=a_ai_collab
#SBATCH --partition=general
#SBATCH --qos=normal
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=12:00:00
#SBATCH --output=/scratch/user/uqaste15/qsmci-repro/hf-upload-%j.out
source ~/miniconda3/etc/profile.d/conda.sh && conda activate qsmxt
set -uo pipefail
cd /scratch/user/uqaste15/qsmci-repro
export HF_TOKEN="${HF_QSMXT_KEY:-}"
export HF_VOLUMES_REPO=qsmxt/qsm-ci-volumes
if [ -z "$HF_TOKEN" ]; then echo "ERROR: HF_TOKEN empty (HF_QSMXT_KEY not propagated to job)"; exit 1; fi
echo "HF_TOKEN present: yes (len ${#HF_TOKEN}) | repo $HF_VOLUMES_REPO"
# 1) concatenate the fresh (eroded matrix + amp-pe-qsmrs addon) runs-json, mtime-gated to exclude the
#    stale Aug GPU pass and the noerode backups.
python3 - <<PY
import json, glob, os, time
LAUNCH=time.mktime(time.strptime("2026-09-01 14:24","%Y-%m-%d %H:%M"))
fresh=sorted(f for f in glob.glob("results/runs-repro-*.json")
             if os.path.getmtime(f)>LAUNCH and "noerode" not in f and "ALL-eroded" not in f)
rows=[]
for f in fresh: rows.extend(json.load(open(f)))
json.dump(rows, open("results/runs-repro-ALL-eroded.json","w"))
print("concatenated", len(fresh), "runs-json ->", len(rows), "runs")
PY
# 2) upload recon + regions.json + resources.json to HF (overwrite matching paths; no delete), patching
#    volume URLs back into the ALL-eroded runs-json for the later index.json merge.
python scripts/publish_volumes.py results --runs results/runs-repro-ALL-eroded.json
echo "HF_UPLOAD_DONE rc=$?"
