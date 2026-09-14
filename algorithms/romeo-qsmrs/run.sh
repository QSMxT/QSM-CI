#!/usr/bin/env bash
set -euo pipefail
IN="${1:-/input}"; OUT="${2:-/output}"

# ROMEO combined multi-echo field mapping (QSM.rs engine, via the QSMxT `fieldmap`
# command): MCPC-3D-S phase-offset removal -> template/temporal multi-echo unwrap ->
# magnitude/TE-weighted B0. Writes the total field in ppm. This replaces the earlier
# per-echo unwrap + unweighted linear fit.
qsmxt fieldmap romeo "$IN/phase.nii.gz" \
  -m "$IN/mask.nii.gz" \
  --magnitude "$IN/magnitude.nii.gz" \
  --params "$IN/params.json" \
  --b0-estimation weighted-avg \
  -o "$OUT/totalfield.nii.gz"
