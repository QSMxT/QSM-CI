#!/usr/bin/env bash
set -euo pipefail
IN="${1:-/input}"; OUT="${2:-/output}"
python3 "$(dirname "$0")/recon.py" "$IN" "$OUT"
