#!/usr/bin/env bash
# QSM-CI submission: SUSEP-Net (chi-separation stage) via QSMxT / QSM.rs, the port of `susep-net`.
set -euo pipefail
IN="${1:-/input}"; OUT="${2:-/output}"

# -o is a PREFIX: qsmxt writes {prefix}_desc-paramagnetic_Chimap.nii and _desc-diamagnetic_
# (the positive magnitude |χ−|, as the contract wants) uncompressed; publish the two gzipped.
B0DIR="${QSMCI_B0_DIR:-0 0 1}"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
qsmxt separate susep-net \
  --qsm "$IN/chimap.nii.gz" --local-field "$IN/localfield.nii.gz" --r2prime "$IN/r2prime.nii.gz" \
  -m "$IN/mask.nii.gz" -o "$WORK/cs" --b0-direction $B0DIR --field-strength "${QSMCI_B0:-3}"
gzip -c "$WORK/cs_desc-paramagnetic_Chimap.nii" > "$OUT/chi-para.nii.gz"
gzip -c "$WORK/cs_desc-diamagnetic_Chimap.nii" > "$OUT/chi-dia.nii.gz"
