#!/usr/bin/env bash
set -euo pipefail
IN="${1:-/input}"; OUT="${2:-/output}"
cp "$IN/localfield.nii.gz" "$OUT/chimap.nii.gz"
