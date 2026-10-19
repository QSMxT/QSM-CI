#!/bin/bash
# Harvest a matrix campaign -> results/repro.json (+ repro_rois.json). Parallel per-shard ROI means
# (each subject's transforms + dseg already built by `repro_eval.py register` + SynthSeg), merged INTO
# the existing repro_rois.json so earlier campaigns' rows are kept, then pairwise TLS fits.
#
#   scripts/repro_slurm/harvest.sh ['results/runs-repro-s0*.json']
#
# The glob (default: every shard file) picks the campaign; its runs replace any rows with the same
# run id, everything else in repro_rois.json stays.
source ~/miniconda3/etc/profile.d/conda.sh && conda activate qsmxt
set -uo pipefail
cd /scratch/user/uqaste15/qsmci-repro

GLOB=${1:-results/runs-repro-*.json}
mapfile -t FRESH < <(compgen -G "$GLOB" | sort)
echo "runs-json in this campaign: ${#FRESH[@]}"

# 1) per-shard ROI means (parallel) -> writes rois back into each runs-json
# SKIP_STATS=1: the rows already carry ROI stats (stream_publish.sh ran them per shard and the
# recon volumes are no longer local), so go straight to the upsert.
[ "${SKIP_STATS:-0}" = 1 ] || printf '%s\n' "${FRESH[@]}" | xargs -P 12 -I{} python scripts/repro_eval.py stats --runs {} > harvest_stats.log 2>&1
echo "stats: $(grep -c 'per-job stats' harvest_stats.log)/${#FRESH[@]} runs-json processed"

# 2) upsert the campaign's rows into results/repro_rois.json
# Files go in argv: `printf | python - <<'PY'` gave the heredoc stdin, so the list read empty.
python - "${FRESH[@]}" <<'PY'
import json, sys
from pathlib import Path
sys.path.insert(0, "scripts")
import repro_eval
p = Path("results/repro_rois.json")
doc = json.loads(p.read_text()) if p.exists() else {"runs": {}}
before = len(doc["runs"])
for f in sys.argv[1:]:
    for r in json.loads(Path(f).read_text()):
        if r.get("rois") and r.get("pipeline"):
            doc["runs"][r["id"]] = {"pipeline": r["pipeline"], "acq": r["phantom"], "rois": r["rois"],
                                    "ref_mean": r.get("ref_mean"), "roi_stats": r.get("roi_stats")}
doc.pop("target", None)
doc["targets"] = repro_eval.subject_targets(repro_eval.repro_acquisitions())
doc.setdefault("roi_labels", {str(k): v for k, v in repro_eval.ROI_LABELS.items()})
p.write_text(json.dumps(doc, indent=2) + "\n")
print(f"repro_rois.json runs: {before} -> {len(doc['runs'])} | distinct pipelines: "
      f"{len({v['pipeline'] for v in doc['runs'].values()})}")
PY

# 3) pairwise TLS fits -> results/repro.json + repro_fits*.bin  (SLOPE_DEV_CAP already rejects diverged/garbage pairs)
python scripts/repro_eval.py fits
echo "HARVEST_DONE $(date +%T)"
