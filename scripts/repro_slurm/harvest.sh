#!/bin/bash
# Harvest the HD-BET repro run -> results/repro.json (+ repro_rois.json). Parallel per-acq ROI means
# (transforms + dseg already built), then pairwise TLS fits. SynthStrip baseline is preserved as
# results/*_synthstrip.json.
source ~/miniconda3/etc/profile.d/conda.sh && conda activate qsmxt
set -uo pipefail
cd /scratch/user/uqaste15/qsmci-repro

touch -d "2026-09-01 14:24" /tmp/ml
mapfile -t FRESH < <(find results -maxdepth 1 -name "runs-repro-*.json" -newer /tmp/ml | sort)
echo "fresh runs-json (this HD-BET run): ${#FRESH[@]}"

# 1) per-acq ROI means (parallel) -> writes rois back into each runs-json
printf '%s\n' "${FRESH[@]}" | xargs -P 12 -I{} python scripts/repro_eval.py stats --runs {} > harvest_stats.log 2>&1
echo "stats: $(grep -c 'per-job stats' harvest_stats.log)/${#FRESH[@]} runs-json processed"

# 2) assemble results/repro_rois.json (phantom->acq) from the fresh runs-json
python - <<'PY'
import json, glob, os, time
LAUNCH = time.mktime(time.strptime("2026-09-01 14:24", "%Y-%m-%d %H:%M"))
fresh = [f for f in glob.glob("results/runs-repro-*.json") if os.path.getmtime(f) > LAUNCH]
try:
    target = json.load(open("data/harmonization/_align/target.json")).get("target", "cima-bridge-run1")
except Exception:
    target = "cima-bridge-run1"
runs = {}
for f in fresh:
    for r in json.load(open(f)):
        if r.get("rois") and r.get("pipeline"):
            runs[r["id"]] = {"pipeline": r["pipeline"], "acq": r["phantom"], "rois": r["rois"],
                             "ref_mean": r.get("ref_mean"), "roi_stats": r.get("roi_stats")}
json.dump({"target": target, "runs": runs}, open("results/repro_rois.json", "w"), indent=2)
print("repro_rois.json runs:", len(runs), "| distinct pipelines:", len({v['pipeline'] for v in runs.values()}))
PY

# 3) pairwise TLS fits -> results/repro.json  (SLOPE_DEV_CAP already rejects diverged/garbage pairs)
python scripts/repro_eval.py fits
echo "HARVEST_DONE $(date +%T)"
