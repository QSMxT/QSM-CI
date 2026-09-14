#!/usr/bin/env bash
# QSM-CI WaveSep submission (iterative wavelet source separation, pure Python on CPU — no MATLAB,
# no GPU, no weights).
#   consumes chimap.nii.gz (χ_total), r2prime.nii.gz, mask.nii.gz, params.json
#   produces chi-para.nii.gz (χ+), chi-dia.nii.gz (χ−)
# The vendored WaveSep source (./wavesep) is baked into the image; recon.py imports it from next to
# this script. In the image `python` has the deps; for a local (--runner local) run set XSEP_PYTHON to
# a python that has numpy/nibabel/pywavelets/scikit-image/scipy/matplotlib/tqdm, and clone the WaveSep
# source into ./wavesep (see BUILD.md).
set -euo pipefail
IN="${1:-/input}"; OUT="${2:-/output}"; DIR="$(cd "$(dirname "$0")" && pwd)"
PY="${XSEP_PYTHON:-python}"
mkdir -p "$OUT"
"$PY" "$DIR/recon.py" "$IN" "$OUT"
