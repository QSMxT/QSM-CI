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
fi
qsmxt bgremove iharperella "$IN/totalfield.nii.gz" -m "$IN/mask.nii.gz" -o "$OUT/localfield.nii.gz" $SET
