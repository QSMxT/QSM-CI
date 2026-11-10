#!/usr/bin/env bash
# QSM-CI submission — LBV (bfr stage) via QSMxT / QSM.rs.
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
  V=$(jq -r '.tol // empty' "$CFG"); [ -n "$V" ] && SET="$SET --tol $V"
  # LBV.m's other settings: only qsmxt after v10.0.0 has them (v10.0.0 refuses the flags, so it
  # runs without them).
  HELP=$(qsmxt bgremove lbv --help 2>/dev/null || true)
  for K in depth peel n1 n2 n3 precision; do
    V=$(jq -r --arg k "$K" '.[$k] // empty' "$CFG")
    [ "$K" = depth ] && [ "$V" = "-1" ] && V=""   # -1: automatic, as LBV.m
    [ -n "$V" ] && grep -q -- "--$K" <<<"$HELP" && SET="$SET --$K $V"
  done
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
# QSMxT after v10.0.0 ports LBV.m's full multigrid (astewartau/QSM.rs#406), whose tolerance is in
# radians over the echo spacing: it needs the field strength and echo times. qsmxt v10.0.0 takes
# neither (its LBV is an SOR solver with a relative tolerance).
SCAN=""
if qsmxt bgremove lbv --help 2>/dev/null | grep -q -- '--field-strength'; then
  SCAN="--field-strength $(jq -r .B0 "$IN/params.json") --echo-times $(jq -r '.TE | map(tostring) | join(" ")' "$IN/params.json")"
fi
qsmxt bgremove lbv "$IN/totalfield.nii.gz" -m "$MASK" -o "$OUT/localfield.nii.gz" --b0-direction $B0 $SCAN $SET
