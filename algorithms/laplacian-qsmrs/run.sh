#!/usr/bin/env bash
set -euo pipefail
IN="${1:-/input}"; OUT="${2:-/output}"

# Laplacian multi-echo field mapping (QSM.rs engine, via the QSMxT `fieldmap` command): each echo
# is Laplacian-unwrapped on its own (Schofield & Zhu; `--laplacian-solver dct`, the default), then
# the echoes are combined into a B0 estimate by the phase-SNR-weighted average
# (`--b0-estimation weighted-avg`, `--b0-weight-type phase-snr`, the default). Writes the total
# field in ppm. No phase-offset removal or bipolar correction (not applied with Laplacian unwrap).

# Parameter overrides (qsm-ci run --set NAME=VALUE) arrive as /input/config.json. Unset, the
# command runs QSMxT's defaults (DCT solve, masked phase, phase-SNR echo weights).
SET=""
CFG="$IN/config.json"
if [ -f "$CFG" ]; then
  V=$(jq -r '.solver // empty' "$CFG"); [ -n "$V" ] && SET="$SET --laplacian-solver $V"
  V=$(jq -r '.fft_pad // empty' "$CFG"); [ -n "$V" ] && SET="$SET --laplacian-fft-pad $V"
  V=$(jq -r '.unmasked // empty' "$CFG"); [ "$V" = "true" ] && SET="$SET --laplacian-unmasked"
  V=$(jq -r '.weighting // empty' "$CFG"); [ -n "$V" ] && SET="$SET --b0-weight-type $V"
fi

qsmxt fieldmap laplacian "$IN/phase.nii.gz" \
  -m "$IN/mask.nii.gz" \
  --magnitude "$IN/magnitude.nii.gz" \
  --params "$IN/params.json" \
  --b0-estimation weighted-avg \
  -o "$OUT/totalfield.nii.gz" $SET
