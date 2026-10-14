#!/usr/bin/env bash
set -euo pipefail
IN="${1:-/input}"; OUT="${2:-/output}"

# Laplacian multi-echo field mapping (QSM.rs engine, via the QSMxT `fieldmap` command): each echo
# is Laplacian-unwrapped on its own (Schofield & Zhu; `--laplacian-solver dct`, the default), then
# the echoes are combined into a B0 estimate by the phase-SNR-weighted average
# (`--b0-estimation weighted-avg`, `--b0-weight-type phase-snr`, the default). Writes the total
# field in ppm. No phase-offset removal or bipolar correction (not applied with Laplacian unwrap).
qsmxt fieldmap laplacian "$IN/phase.nii.gz" \
  -m "$IN/mask.nii.gz" \
  --magnitude "$IN/magnitude.nii.gz" \
  --params "$IN/params.json" \
  --b0-estimation weighted-avg \
  -o "$OUT/totalfield.nii.gz"
