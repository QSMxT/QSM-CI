#!/usr/bin/env bash
# Runs the MATLAB-compiled `recon` binary (mounted at /algo) on the MATLAB Runtime.
set -euo pipefail
IN="${1:-/input}"; OUT="${2:-/output}"
DIR="$(cd "$(dirname "$0")" && pwd)"
"$DIR/recon" "$IN" "$OUT"    # the MCR wrapper sets LD_LIBRARY_PATH
