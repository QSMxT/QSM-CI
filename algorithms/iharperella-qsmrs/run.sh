#!/usr/bin/env bash
# QSM-CI submission — iHARPERELLA (unwrap+bfr stage) via QSMxT / QSM.rs.
set -euo pipefail
IN="${1:-/input}"; OUT="${2:-/output}"

# iHARPERELLA unwraps and removes the background from one WRAPPED echo: the first echo of the 4D
# phase (qsmxt reads the first volume). Given that echo's --te and --field-strength, qsmxt >= v10.0.0
# treats the input as wrapped phase in rad and writes the local field in ppm (without both flags it
# would read the input as an unwrapped total field in ppm instead).
B0=$(jq -r '.B0' "$IN/params.json")
TE=$(jq -r '.TE[0]' "$IN/params.json")

# Parameter overrides (qsm-ci run --set NAME=VALUE) arrive as /input/config.json.
SET=""
CFG="$IN/config.json"
if [ -f "$CFG" ]; then
  V=$(jq -r '.max_iter // empty' "$CFG"); [ -n "$V" ] && SET="$SET --max-iter $V"
  V=$(jq -r '.tol // empty' "$CFG"); [ -n "$V" ] && SET="$SET --tol $V"
fi
qsmxt bgremove iharperella "$IN/phase.nii.gz" -m "$IN/mask.nii.gz" -o "$OUT/localfield.nii.gz" \
  --te "$TE" --field-strength "$B0" $SET
