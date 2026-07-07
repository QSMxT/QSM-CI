#!/usr/bin/env bash
# Reference QSM-CI submission entrypoint.
#
# Contract v1: read /input, write /output/chimap.nii.gz (ppm, within mask).
# This example shells out to a `qsm` CLI baked into the image; replace the middle
# section with your own reconstruction in whatever language you like.
set -euo pipefail

INPUT=/input
OUTPUT=/output

echo "[example-tkd] inputs:"
ls -la "$INPUT"
echo "[example-tkd] params:"
cat "$INPUT/params.json"

# --- your reconstruction goes here -------------------------------------------
# Produce a total field from the multi-echo phase, remove the background field,
# then invert the dipole with TKD. Here we assume a `qsm` binary in the image
# that implements the full pipeline; a real submission would call its own code.
qsm pipeline \
  --phase "$INPUT/phase.nii.gz" \
  --magnitude "$INPUT/magnitude.nii.gz" \
  --mask "$INPUT/mask.nii.gz" \
  --params "$INPUT/params.json" \
  --inversion tkd \
  --output "$OUTPUT/chimap.nii.gz"
# -----------------------------------------------------------------------------

echo "[example-tkd] wrote:"
ls -la "$OUTPUT/chimap.nii.gz"
