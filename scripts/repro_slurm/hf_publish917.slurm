#!/bin/bash
#SBATCH --job-name=hf-publish917
#SBATCH --account=a_ai_collab
#SBATCH --partition=general
#SBATCH --qos=normal
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=12:00:00
#SBATCH --output=/scratch/user/uqaste15/qsmci-repro/hf-publish917-%j.out
# Merge this run's shards into index.json, then publish to HF in INDEX mode so --prune can work
# (--prune is refused with --runs: a shard publish cannot tell an orphan from another shard's file).
# This first pass is a DRY RUN — it uploads, then reports what pruning WOULD delete, deleting nothing.
source ~/miniconda3/etc/profile.d/conda.sh && conda activate qsmxt
set -uo pipefail
cd /scratch/user/uqaste15/qsmci-repro
eval "$(grep '^export HF_QSMXT_KEY=' ~/.bashrc)" 2>/dev/null || true
export HF_TOKEN="${HF_QSMXT_KEY:-}"
export HF_VOLUMES_REPO=qsmxt/qsm-ci-volumes
if [ -z "$HF_TOKEN" ]; then echo "ERROR: HF_TOKEN empty (HF_QSMXT_KEY not in ~/.bashrc)"; exit 1; fi
echo "HF_TOKEN present (len ${#HF_TOKEN}) | repo $HF_VOLUMES_REPO"

# ---- merge THIS run's shards into results/index.json (upsert by id, order preserved) ----------
python - <<'PY'
import glob, json, os, time
from pathlib import Path
LAUNCH = time.mktime(time.strptime("2026-09-08 12:00", "%Y-%m-%d %H:%M"))
fresh = sorted(f for f in glob.glob("results/runs-repro-*.json") if os.path.getmtime(f) > LAUNCH)
idx_p = Path("results/index.json")
doc = json.loads(idx_p.read_text()) if idx_p.exists() else {"runs": []}
runs = {r["id"]: r for r in doc.get("runs", [])}
order = [r["id"] for r in doc.get("runs", [])]
n_new = 0
for f in fresh:
    for r in json.loads(Path(f).read_text()):
        if r["id"] not in runs:
            order.append(r["id"]); n_new += 1
        runs[r["id"]] = r
doc["runs"] = [runs[i] for i in order]
doc["generated"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
idx_p.write_text(json.dumps(doc, indent=2) + "\n")
print(f"merged {len(fresh)} shard files ({n_new} new runs, {len(order)} total in index.json)")
PY

# ---- publish (index mode) + report what pruning would remove ---------------------------------
python scripts/publish_volumes.py results --prune-dry-run
echo "HF_PUBLISH917_DONE rc=$?"
