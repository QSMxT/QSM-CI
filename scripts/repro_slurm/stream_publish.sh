#!/bin/bash
# After one matrix shard: ROI stats -> upload its volumes to HF -> drop the local recon volumes that
# landed. The full matrix's recons (~340 GB) don't fit in user scratch, so they live on the Hub; the
# runs-json keeps the rows, ROI stats and volume URLs (harvest.sh with SKIP_STATS=1 merges them).
#   scripts/repro_slurm/stream_publish.sh results/<prefix>-<acq>-s<k>.json
set -uo pipefail
F=$1
python scripts/repro_eval.py stats --runs "$F" || echo "STREAM_STATS_FAILED $F"
HF_TOKEN="$(cat ~/.hf_publish_token)" HF_VOLUMES_REPO=qsmxt/qsm-ci-volumes \
  python scripts/publish_volumes.py results --runs "$F" || echo "STREAM_PUBLISH_FAILED $F"
python - "$F" <<'PY'
import json, os, sys
rows = json.load(open(sys.argv[1])); n = kept = 0
for r in rows:
    if r.get("status") != "ok":
        continue
    p = os.path.join("results", r["id"], "recon.nii.gz")
    if (r.get("volumes") or {}).get("recon") and not r.get("volumes_stale"):
        if os.path.exists(p):
            os.remove(p); n += 1
    elif os.path.exists(p):
        kept += 1
print(f"stream: dropped {n} local recon volumes now on HF; kept {kept} not (yet) uploaded")
PY
