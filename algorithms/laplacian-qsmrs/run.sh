#!/usr/bin/env bash
set -euo pipefail
IN="${1:-/input}"; OUT="${2:-/output}"

# Laplacian multi-echo field mapping (QSM.rs engine, via the QSMxT `fieldmap` command): each echo
# is Laplacian-unwrapped on its own (Schofield & Zhu; `--laplacian-solver dct`, the default), then
# the echoes are combined into a B0 estimate by the phase-SNR-weighted average
# (`--b0-estimation weighted-avg`, `--b0-weight-type phase-snr`, the default). Writes the total
# field in ppm. No phase-offset removal or bipolar correction.
#
# Phase offsets: since QSMxT v12.2.0, `fieldmap laplacian` removes them first by default
# (MCPC-3D-S, `--phase-offset-removal`). This entry keeps them in (`phase_offset_removal: false`):
# the `laplacian` parity pair's reference, QSM.jl's Laplacian unwrap, removes none, and the bridge
# datasets' parity pairs chain their inputs from this method with its defaults. Earlier qsmxt
# releases have no such flag and never removed offsets with Laplacian unwrap, so the default is
# passed only where `--help` lists it; an explicit `--set phase_offset_removal=...` is always passed.

# Parameter overrides (qsm-ci run --set NAME=VALUE) arrive as /input/config.json. Unset, the
# command runs QSMxT's defaults (DCT solve, masked phase, phase-SNR echo weights), except that the
# phase offsets are kept in (above).
SET=""
OFFSETS=""
CFG="$IN/config.json"
if [ -f "$CFG" ]; then
  V=$(jq -r '.solver // empty' "$CFG"); [ -n "$V" ] && SET="$SET --laplacian-solver $V"
  V=$(jq -r '.fft_pad // empty' "$CFG"); [ -n "$V" ] && SET="$SET --laplacian-fft-pad $V"
  V=$(jq -r '.unmasked // empty' "$CFG"); [ "$V" = "true" ] && SET="$SET --laplacian-unmasked"
  V=$(jq -r '.weighting // empty' "$CFG"); [ -n "$V" ] && SET="$SET --b0-weight-type $V"
  V=$(jq -r '.b0_estimation // empty' "$CFG"); [ -n "$V" ] && B0EST="$V"
  # `has`, not `//`: jq's `//` drops an explicit false.
  OFFSETS=$(jq -r 'if has("phase_offset_removal") then .phase_offset_removal | tostring else empty end' "$CFG")
fi
if [ -n "$OFFSETS" ]; then
  SET="$SET --phase-offset-removal $OFFSETS"
elif qsmxt fieldmap laplacian --help 2>/dev/null | grep -q -- '--phase-offset-removal'; then
  SET="$SET --phase-offset-removal false"
fi
# QSMART's echo fit also writes its reliability map R_0, beside the field, for QSMART to read.
[ "${B0EST:-weighted-avg}" = "qsmart-echofit" ] && SET="$SET --reliability-output $OUT/reliability.nii.gz"

qsmxt fieldmap laplacian "$IN/phase.nii.gz" \
  -m "$IN/mask.nii.gz" \
  --magnitude "$IN/magnitude.nii.gz" \
  --params "$IN/params.json" \
  --b0-estimation "${B0EST:-weighted-avg}" \
  -o "$OUT/totalfield.nii.gz" $SET
