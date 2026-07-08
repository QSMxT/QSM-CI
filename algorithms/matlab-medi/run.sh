#!/usr/bin/env bash
# Runs the MATLAB-compiled `recon` on the free MATLAB Runtime (no license at run time).
# The binary is either baked into the image at /opt/qsm-ci/recon (recommended) or committed
# alongside this script and mounted at /algo. No network needed.
set -euo pipefail
IN="${1:-/input}"; OUT="${2:-/output}"
DIR="$(cd "$(dirname "$0")" && pwd)"
BIN="${MATLAB_RECON:-/opt/qsm-ci/recon}"
[ -x "$BIN" ] || BIN="$DIR/recon"
exec "$BIN" "$IN" "$OUT"    # the MCR wrapper sets LD_LIBRARY_PATH
