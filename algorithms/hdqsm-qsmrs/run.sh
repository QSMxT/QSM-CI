#!/usr/bin/env bash
# QSM-CI submission — HD-QSM (dipole stage) via QSMxT / QSM.rs.
set -euo pipefail
IN="${1:-/input}"; OUT="${2:-/output}"
B0=$(jq -r '.B0_dir | join(" ")' "$IN/params.json")

# Parameter overrides (qsm-ci run --set NAME=VALUE) arrive as /input/config.json.
SET=""
CFG="$IN/config.json"
if [ -f "$CFG" ]; then
  V=$(jq -r '.alpha_l2 // empty' "$CFG"); [ -n "$V" ] && SET="$SET --alpha-l2 $V"
  V=$(jq -r '.mu1_l2 // empty' "$CFG"); [ -n "$V" ] && SET="$SET --mu1-l2 $V"
  V=$(jq -r '.max_iter_l1 // empty' "$CFG"); [ -n "$V" ] && SET="$SET --max-iter-l1 $V"
  V=$(jq -r '.max_iter_l2 // empty' "$CFG"); [ -n "$V" ] && SET="$SET --max-iter-l2 $V"
  V=$(jq -r '.tol_update // empty' "$CFG"); [ -n "$V" ] && SET="$SET --tol-update $V"
fi
# QSMxT after v10.0.0 weights HD-QSM's data term by the magnitude, mask·mag/max(mag) (HDQSM.m's
# usage example, astewartau/QSM.rs#241); several echoes are combined by root sum of squares. qsmxt
# v10.0.0 has no --magnitude.
MAG=""
if qsmxt invert hdqsm --help 2>/dev/null | grep -q -- '--magnitude'; then MAG="--magnitude $IN/magnitude.nii.gz"; fi
qsmxt invert hdqsm "$IN/localfield.nii.gz" -m "$IN/mask.nii.gz" -o "$OUT/chimap.nii.gz" --b0-direction $B0 $MAG $SET
