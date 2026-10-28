#!/usr/bin/env bash
# QSM-CI submission: HD-BET (brain-extraction stage) via QSMxT / QSM.rs, the port of `hd-bet-qsmci`.
set -euo pipefail
IN="${1:-/input}"; OUT="${2:-/output}"

# HD-BET without test-time augmentation, as the `hd-bet-qsmci` entry runs it. On a multi-echo
# magnitude `qsmxt mask` reads the first echo, where `hd-bet-qsmci` combines the echoes by
# root-sum-of-squares first (fidelity/dl/README.md).
qsmxt mask hd-bet "$IN/magnitude.nii.gz" -o "$OUT/mask.nii.gz"
