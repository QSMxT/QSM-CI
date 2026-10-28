#!/usr/bin/env bash
# QSM-CI submission: BFRnet (bfr stage) via QSMxT / QSM.rs, the port of `bfrnet`.
set -euo pipefail
IN="${1:-/input}"; OUT="${2:-/output}"

# B0 direction and field strength from params.json (QSMCI_* env, CONTRACT.md).
B0DIR="${QSMCI_B0_DIR:-0 0 1}"
qsmxt bgremove bfrnet "$IN/totalfield.nii.gz" -m "$IN/mask.nii.gz" -o "$OUT/localfield.nii.gz" \
  --b0-direction $B0DIR
