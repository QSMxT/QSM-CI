#!/usr/bin/env bash
# QSM-CI submission — WH-QSM (dipole stage) via QSMxT / QSM.rs.
set -euo pipefail
IN="${1:-/input}"; OUT="${2:-/output}"
B0=$(jq -r '.B0_dir | join(" ")' "$IN/params.json")

# Parameter overrides (qsm-ci run --set NAME=VALUE) arrive as /input/config.json.
SET=""
CFG="$IN/config.json"
if [ -f "$CFG" ]; then
  V=$(jq -r '.alpha1 // empty' "$CFG"); [ -n "$V" ] && SET="$SET --alpha1 $V"
  V=$(jq -r '.mu1 // empty' "$CFG"); [ -n "$V" ] && SET="$SET --mu1 $V"
  V=$(jq -r '.beta // empty' "$CFG"); [ -n "$V" ] && SET="$SET --beta $V"
  V=$(jq -r '.max_iter // empty' "$CFG"); [ -n "$V" ] && SET="$SET --max-iter $V"
  V=$(jq -r '.tol_update // empty' "$CFG"); [ -n "$V" ] && SET="$SET --tol-update $V"
fi
# QSMxT after v10.0.0: WH-QSM (WH_nlTV.m, astewartau/QSM.rs#233) converts the field to phase at the
# first echo time and needs the field strength and echo times for it; its default weight is
# WH_nlTV.m's flat one, so no magnitude. qsmxt v10.0.0 takes neither.
SCAN=""
if qsmxt invert whqsm --help 2>/dev/null | grep -q -- '--field-strength'; then
  SCAN="--field-strength $(jq -r .B0 "$IN/params.json") --echo-times $(jq -r '.TE | map(tostring) | join(" ")' "$IN/params.json")"
fi
qsmxt invert whqsm "$IN/localfield.nii.gz" -m "$IN/mask.nii.gz" -o "$OUT/chimap.nii.gz" --b0-direction $B0 $SCAN $SET
