#!/usr/bin/env bash
# QSM-CI submission: MindGrab (brain-extraction stage) via QSMxT / QSM.rs.
set -euo pipefail
IN="${1:-/input}"; OUT="${2:-/output}"

# On a multi-echo magnitude `qsmxt mask` reads the first echo.
qsmxt mask mindgrab "$IN/magnitude.nii.gz" -o "$OUT/mask.nii.gz"
