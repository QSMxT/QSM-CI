#!/usr/bin/env bash
set -euo pipefail
IN="${1:-/input}"; OUT="${2:-/output}"
cp "$IN/totalfield.nii.gz" "$OUT/localfield.nii.gz"
