#!/usr/bin/env bash
# QSM-CI submission — TV (ADMM) (dipole stage) via QSMxT / QSM.rs.
set -euo pipefail
IN="${1:-/input}"; OUT="${2:-/output}"
B0=$(jq -r '.B0_dir | join(" ")' "$IN/params.json")

# Parameter overrides (qsm-ci run --set NAME=VALUE) arrive as /input/config.json.
SET=""
CFG="$IN/config.json"
if [ -f "$CFG" ]; then
  V=$(jq -r '.lambda // empty' "$CFG"); [ -n "$V" ] && SET="$SET --lambda $V"
  V=$(jq -r '.rho // empty' "$CFG"); [ -n "$V" ] && SET="$SET --rho $V"
  V=$(jq -r '.max_iter // empty' "$CFG"); [ -n "$V" ] && SET="$SET --max-iter $V"
fi
qsmxt invert tv "$IN/localfield.nii.gz" -m "$IN/mask.nii.gz" -o "$OUT/chimap.nii.gz" --b0-direction $B0 $SET
