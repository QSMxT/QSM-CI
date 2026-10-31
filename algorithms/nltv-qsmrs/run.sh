#!/usr/bin/env bash
# QSM-CI submission — NLTV (dipole stage) via QSMxT / QSM.rs.
set -euo pipefail
IN="${1:-/input}"; OUT="${2:-/output}"
# Acquisition parameters are injected as env vars — no need to parse params.json/config.json:
#   $QSMCI_B0 (T)   $QSMCI_TE / $QSMCI_TE0 (s)   $QSMCI_B0_DIR   $QSMCI_VOXEL_SIZE (mm)
#   $QSMCI_SET_<NAME>  for each  qsm-ci run --set NAME=VALUE  override
B0=$(jq -r '.B0_dir | join(" ")' "$IN/params.json")

# Parameter overrides (qsm-ci run --set NAME=VALUE) arrive as /input/config.json.
SET=""
CFG="$IN/config.json"
if [ -f "$CFG" ]; then
  V=$(jq -r '.lambda // empty' "$CFG"); [ -n "$V" ] && SET="$SET --lambda $V"
  V=$(jq -r '.max_iter // empty' "$CFG"); [ -n "$V" ] && SET="$SET --max-iter $V"
fi
# QSM.rs's NLTV (QSM.jl's `nltv`, astewartau/QSM.rs#323) converts the field to phase at the first
# echo time and requires the magnitude as its data weight; qsmxt v10.0.0's NLTV (a different,
# reweighted-TV algorithm) takes neither.
if qsmxt invert nltv --help 2>/dev/null | grep -q -- '--magnitude'; then
  FS=$(jq -r .B0 "$IN/params.json"); TES=$(jq -r '.TE | map(tostring) | join(" ")' "$IN/params.json")
  exec qsmxt invert nltv "$IN/localfield.nii.gz" -m "$IN/mask.nii.gz" -o "$OUT/chimap.nii.gz" \
    --b0-direction $B0 --field-strength "$FS" --echo-times $TES --magnitude "$IN/magnitude.nii.gz" $SET
fi
qsmxt invert nltv "$IN/localfield.nii.gz" -m "$IN/mask.nii.gz" -o "$OUT/chimap.nii.gz" --b0-direction $B0 $SET
