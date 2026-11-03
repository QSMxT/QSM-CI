#!/usr/bin/env bash
# QSM-CI submission: NeXtQSM (bfr+dipole stage) via QSMxT / QSM.rs, the port of `nextqsm`.
set -euo pipefail
IN="${1:-/input}"; OUT="${2:-/output}"

# B0 direction and field strength from params.json (QSMCI_* env, CONTRACT.md).
B0DIR="${QSMCI_B0_DIR:-0 0 1}"
qsmxt invert nextqsm "$IN/totalfield.nii.gz" -m "$IN/mask.nii.gz" -o "$OUT/chimap.nii.gz" \
  --b0-direction $B0DIR --field-strength "${QSMCI_B0:-3}"
