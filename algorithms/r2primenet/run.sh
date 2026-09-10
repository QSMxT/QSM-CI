#!/usr/bin/env bash
# QSM-CI R2PRIMEnet submission (deep learning, ONNX via onnxruntime — no MATLAB).
#   consumes magnitude.nii.gz, mask.nii.gz, params.json
#   produces r2prime.nii.gz (Hz)
# Model + norm stats are baked into the image at $XSEPNET_MODELS; recon.py falls back to a local copy
# (next to it) or $CHISEP_TOOLBOX/models outside the container. In the image `python` has onnxruntime;
# for a local (--runner local) run, set XSEP_PYTHON to a python that does.
set -euo pipefail
IN="${1:-/input}"; OUT="${2:-/output}"; DIR="$(cd "$(dirname "$0")" && pwd)"
PY="${XSEP_PYTHON:-python}"
mkdir -p "$OUT"
"$PY" "$DIR/recon.py" "$IN" "$OUT"
