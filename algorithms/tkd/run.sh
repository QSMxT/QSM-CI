#!/usr/bin/env bash
# QSM-CI entrypoint. Defaults to the container mounts (/input, /output); accepts explicit dirs so
# the local runner (scripts/pipeline.py) can drive it without Docker.
set -euo pipefail
IN="${1:-/input}"; OUT="${2:-/output}"
python3 "$(dirname "$0")/recon.py" "$IN" "$OUT"
