#!/usr/bin/env bash
# QSM-CI submission: MindGrab (brain-extraction stage) via QSMxT / QSM.rs.
set -euo pipefail
IN="${1:-/input}"; OUT="${2:-/output}"

# On a multi-echo magnitude, qsmxt v10.0.0 reads the first echo; later qsmxt combines the echoes by
# root-sum-of-squares, as the `mindgrab` original does.
qsmxt mask mindgrab "$IN/magnitude.nii.gz" -o "$OUT/mask.nii.gz"
