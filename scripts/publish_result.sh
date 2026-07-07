#!/usr/bin/env bash
# Record a run's result: append/replace its entry in results/index.json, drop the per-run JSON,
# and copy the viewer volumes (recon / truth / error) next to it for the static site.
#
# Usage: publish_result.sh <slug> <track> <status> <metrics.json> <recon.nii.gz> <truth.nii.gz>
set -euo pipefail

SLUG="${1:?}"; TRACK="${2:?}"; STATUS="${3:?}"
METRICS="${4:?}"; RECON="${5:?}"; TRUTH="${6:?}"

RUN_ID="${SLUG}-${TRACK}-${GITHUB_RUN_ID:-local}"
DEST="results/${SLUG}/${TRACK}"
mkdir -p "$DEST"

# Per-run detail JSON (from qsm-eval, plus status/id).
if [ "$STATUS" = "ok" ] && [ -f "$METRICS" ]; then
  jq --arg id "$RUN_ID" --arg slug "$SLUG" --arg status "$STATUS" \
     '. + {id:$id, slug:$slug, status:$status}' "$METRICS" > "$DEST/run.json"
  # Viewer volumes served statically by the site.
  cp "$RECON" "$DEST/recon.nii.gz"
  cp "$TRUTH" "$DEST/truth.nii.gz"
  # Signed error map for the overlay (recon - truth). TODO: compute with a tiny helper/qsm-eval.
  # cp error.nii.gz "$DEST/error.nii.gz"
else
  jq -n --arg id "$RUN_ID" --arg slug "$SLUG" --arg track "$TRACK" --arg status "$STATUS" \
     '{id:$id, slug:$slug, track:$track, status:$status, metrics:null}' > "$DEST/run.json"
fi

# Merge into the flat leaderboard index (drop any prior entry for this id, append the new one).
python3 - "$RUN_ID" "$DEST/run.json" <<'PY'
import json, sys, pathlib
run_id, run_path = sys.argv[1], sys.argv[2]
idx_path = pathlib.Path("results/index.json")
idx = json.loads(idx_path.read_text())
run = json.loads(pathlib.Path(run_path).read_text())
idx["runs"] = [r for r in idx.get("runs", []) if r.get("id") != run_id] + [run]
idx_path.write_text(json.dumps(idx, indent=2) + "\n")
PY

echo "[publish_result] recorded $RUN_ID (status=$STATUS)"
