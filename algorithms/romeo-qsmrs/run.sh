#!/usr/bin/env bash
set -euo pipefail
IN="${1:-/input}"; OUT="${2:-/output}"

# ROMEO combined multi-echo field mapping (QSM.rs engine, via the QSMxT `fieldmap`
# command): MCPC-3D-S phase-offset removal -> template/temporal multi-echo unwrap ->
# magnitude/TE-weighted B0. Writes the total field in ppm. This replaces the earlier
# per-echo unwrap + unweighted linear fit.
# Parameter overrides (qsm-ci run --set NAME=VALUE) arrive as /input/config.json. Unset, qsmxt's
# own defaults apply. The flags exist in every qsmxt that has `fieldmap romeo` (v11.0.0 on).
SET=""
CFG="$IN/config.json"
if [ -f "$CFG" ]; then
  V=$(jq -r '.individual_unwrapping // empty' "$CFG")
  case "$V" in true) SET="$SET --romeo-individual";; false) SET="$SET --no-romeo-individual";; esac
  V=$(jq -r '.correct_global // empty' "$CFG")
  case "$V" in true) SET="$SET --romeo-correct-global";; false) SET="$SET --no-romeo-correct-global";; esac
fi
qsmxt fieldmap romeo "$IN/phase.nii.gz" \
  -m "$IN/mask.nii.gz" \
  --magnitude "$IN/magnitude.nii.gz" \
  --params "$IN/params.json" \
  --b0-estimation weighted-avg \
  -o "$OUT/totalfield.nii.gz" $SET
