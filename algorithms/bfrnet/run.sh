#!/usr/bin/env bash
# QSM-CI submission — BFRnet (bfr stage) via ONNX Runtime (no MATLAB).
# recon.py is mounted at /algo; the ONNX weights are baked into the image at /opt/bfrnet/BFRnet.onnx.
set -euo pipefail
IN="${1:-/input}"; OUT="${2:-/output}"
DIR="$(cd "$(dirname "$0")" && pwd)"
exec python3 "$DIR/recon.py" "$IN" "$OUT"
