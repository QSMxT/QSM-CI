#!/usr/bin/env bash
# QSM-CI SUSEP-Net submission (deep learning, PyTorch on CPU — no MATLAB, no GPU).
#   consumes localfield.nii.gz, chimap.nii.gz, r2prime.nii.gz, magnitude.nii.gz, mask.nii.gz, params.json
#   produces chi-para.nii.gz (χ+), chi-dia.nii.gz (χ−)
# Weights (SUSEPNet.pth) + norm stats are baked into the image at $SUSEPNET_MODELS; recon.py falls back
# to a local copy (next to it) outside the container. In the image `python` has torch; for a local
# (--runner local) run, set XSEP_PYTHON to a python that does.
set -euo pipefail
IN="${1:-/input}"; OUT="${2:-/output}"; DIR="$(cd "$(dirname "$0")" && pwd)"
PY="${XSEP_PYTHON:-python}"
mkdir -p "$OUT"
"$PY" "$DIR/recon.py" "$IN" "$OUT"
