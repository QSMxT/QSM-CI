#!/usr/bin/env bash
# QSM-CI QSMnetME submission (dipole stage; deep learning, ONNX via onnxruntime — no MATLAB).
#   consumes localfield.nii.gz, mask.nii.gz, params.json  ->  produces chimap.nii.gz
# The toolbox's networks + norm stats are baked into the image at $XSEPNET_MODELS; recon.py falls
# back to a copy next to it or $CHISEP_TOOLBOX/models. For a local run set XSEP_PYTHON to a python
# with numpy, scipy, nibabel, onnx and onnxruntime.
set -euo pipefail
IN="${1:-/input}"; OUT="${2:-/output}"; DIR="$(cd "$(dirname "$0")" && pwd)"
PY="${XSEP_PYTHON:-python}"
mkdir -p "$OUT"
"$PY" "$DIR/recon.py" "$IN" "$OUT"
