#!/usr/bin/env bash
# QSM-CI submission — iHARPERELLA (bfr stage) via QSMxT / QSM.rs.
set -euo pipefail
IN="${1:-/input}"; OUT="${2:-/output}"

# iHARPERELLA on the multi-echo total field in ppm (no --te/--field-strength, so qsmxt reads the input
# as an unwrapped field and uses the ordinary Laplacian), as `qsmxt run` does. The published method
# starts from one wrapped echo instead; on in-vivo data a single echo was far noisier.
# Parameter overrides (qsm-ci run --set NAME=VALUE) arrive as /input/config.json.
SET=""
CFG="$IN/config.json"
if [ -f "$CFG" ]; then
  V=$(jq -r '.max_iter // empty' "$CFG"); [ -n "$V" ] && SET="$SET --max-iter $V"
  V=$(jq -r '.tol // empty' "$CFG"); [ -n "$V" ] && SET="$SET --tol $V"
  V=$(jq -r '.rim // empty' "$CFG"); [ -n "$V" ] && SET="$SET --rim $V"   # sti | whole (qsmxt from v12.0.0)
fi
# erode_voxels: erode the mask by N voxels before background removal, as `qsmxt run
# --bf-erode-voxels` does (the same 6-connected erosion); the field is left whole, and the local
# field is 0 outside the eroded mask. 0 (default): the mask as given.
MASK="$IN/mask.nii.gz"
ERODE=0
[ -f "$CFG" ] && ERODE=$(jq -r '.erode_voxels // 0' "$CFG")
if [ "$ERODE" -gt 0 ]; then
  MASK="$(mktemp -d)/mask_eroded.nii.gz"
  qsmxt mask erode "$IN/mask.nii.gz" -o "$MASK" --iterations "$ERODE"
fi
qsmxt bgremove iharperella "$IN/totalfield.nii.gz" -m "$MASK" -o "$OUT/localfield.nii.gz" $SET
