#!/usr/bin/env bash
# QSM-CI submission — V-SHARP (bfr stage) via QSMxT / QSM.rs.
set -euo pipefail
IN="${1:-/input}"; OUT="${2:-/output}"
# Acquisition parameters are injected as env vars — no need to parse params.json/config.json:
#   $QSMCI_B0 (T)   $QSMCI_TE / $QSMCI_TE0 (s)   $QSMCI_B0_DIR   $QSMCI_VOXEL_SIZE (mm)
#   $QSMCI_SET_<NAME>  for each  qsm-ci run --set NAME=VALUE  override
B0=$(jq -r '.B0_dir | join(" ")' "$IN/params.json")

# QSMxT's default: no deconvolution. Deconvolving (TSVD, threshold 0.05) is the sim-tuned value
# (xSIM 0.845, vs 0.820 at threshold 0.2 and 0.803 without), passed as --set deconvolve=true.
# Parameter overrides (qsm-ci run --set NAME=VALUE) arrive as /input/config.json.
DECONVOLVE=false; THRESHOLD=0.05; SET=""
CFG="$IN/config.json"
if [ -f "$CFG" ]; then
  # Not `.deconvolve // empty`: jq's `//` treats `false` as absent.
  V=$(jq -r 'if has("deconvolve") then .deconvolve | tostring else empty end' "$CFG")
  # Lower-cased: a tuned value can arrive as Python's "True".
  [ -n "$V" ] && DECONVOLVE=$(printf '%s' "$V" | tr '[:upper:]' '[:lower:]')
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
