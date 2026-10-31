#!/usr/bin/env bash
# QSM-CI submission: HD-BET (brain-extraction stage) via QSMxT / QSM.rs, the port of `hd-bet-qsmci`.
set -euo pipefail
IN="${1:-/input}"; OUT="${2:-/output}"

# HD-BET without test-time augmentation, as the `hd-bet-qsmci` entry runs it. A multi-echo
# magnitude: qsmxt v10.0.0 reads the first echo; later qsmxt combines the echoes by
# root-sum-of-squares first, as `hd-bet-qsmci` does (fidelity/dl/README.md).
SET=""
CFG="$IN/config.json"
if [ -f "$CFG" ]; then
  # HD-BET's own sliding window (192x192x96 patches, step 0.5) in place of QSM.rs's whole-volume
  # default, for the hd-bet parity pair: run that way, the port reproduces the original
  # (astewartau/QSM.rs#330).
  V=$(jq -r 'if has("window") then .window | tostring else empty end' "$CFG")
  if [ "$V" = true ]; then SET="$SET --window"; fi
fi
qsmxt mask hd-bet "$IN/magnitude.nii.gz" -o "$OUT/mask.nii.gz" $SET
