#!/usr/bin/env bash
# QSM-CI submission — V-SHARP (bfr stage) via QSMxT / QSM.rs.
set -euo pipefail
IN="${1:-/input}"; OUT="${2:-/output}"
# Acquisition parameters are injected as env vars — no need to parse params.json/config.json:
#   $QSMCI_B0 (T)   $QSMCI_TE / $QSMCI_TE0 (s)   $QSMCI_B0_DIR   $QSMCI_VOXEL_SIZE (mm)
#   $QSMCI_SET_<NAME>  for each  qsm-ci run --set NAME=VALUE  override
B0=$(jq -r '.B0_dir | join(" ")' "$IN/params.json")

# QSM-CI deconvolves (TSVD, threshold 0.05) although qsmxt v10's default is not to: on the sim
# phantom that scored best (xSIM 0.845, vs 0.820 at threshold 0.2 and 0.803 without).
# Parameter overrides (qsm-ci run --set NAME=VALUE) arrive as /input/config.json.
DECONVOLVE=true; THRESHOLD=0.05; SET=""
CFG="$IN/config.json"
if [ -f "$CFG" ]; then
  # Not `.deconvolve // empty`: jq's `//` treats `false` as absent, which silently kept
  # deconvolve=true for `--set deconvolve=false`.
  V=$(jq -r 'if has("deconvolve") then .deconvolve | tostring else empty end' "$CFG")
  [ -n "$V" ] && DECONVOLVE=$V
  V=$(jq -r '.threshold // empty' "$CFG"); [ -n "$V" ] && THRESHOLD=$V
  V=$(jq -r '.max_radius // empty' "$CFG"); [ -n "$V" ] && SET="$SET --max-radius $V"
  V=$(jq -r '.min_radius // empty' "$CFG"); [ -n "$V" ] && SET="$SET --min-radius $V"
  # default or qsmjl (QSM.jl's SMV ball), for the vsharp-qsmjl parity pair (qsmxt after v10.0.0,
  # QSMxT/QSMxT#460; an older qsmxt refuses the flag).
  V=$(jq -r '.ball // empty' "$CFG"); [ -n "$V" ] && SET="$SET --ball $V"
  # Working grid: isotropic (QSM.rs's default, 1 mm), native or finest (qsmxt bgremove vsharp --grid).
  V=$(jq -r '.grid // empty' "$CFG"); [ -n "$V" ] && SET="$SET --grid $V"
  V=$(jq -r '.radius_step // empty' "$CFG"); [ -n "$V" ] && SET="$SET --radius-step $V"
fi
# --threshold only applies with deconvolution (qsmxt ignores it otherwise).
[ "$DECONVOLVE" = true ] && SET="$SET --threshold $THRESHOLD"
qsmxt bgremove vsharp "$IN/totalfield.nii.gz" -m "$IN/mask.nii.gz" -o "$OUT/localfield.nii.gz" \
  --b0-direction $B0 --deconvolve "$DECONVOLVE" $SET
