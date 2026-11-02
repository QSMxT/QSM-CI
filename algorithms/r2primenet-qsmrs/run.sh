#!/usr/bin/env bash
# QSM-CI submission: R2PRIMEnet (r2prime-generation: multi-echo magnitude → R2′) via QSMxT / QSM.rs,
# the port of `r2primenet`.
set -euo pipefail
IN="${1:-/input}"; OUT="${2:-/output}"

FIELD="${QSMCI_B0:-$(jq -r .B0 "$IN/params.json")}"
TES="${QSMCI_TE:-$(jq -r '.TE | map(tostring) | join(" ")' "$IN/params.json")}"
SET=""
CFG="$IN/config.json"
if [ -f "$CFG" ] && jq -e '.ignore_field_mismatch == true or .ignore_field_mismatch == "true"' "$CFG" >/dev/null; then
  SET="--r2primenet-ignore-field-mismatch"
fi

# R2* by ARLO (MEDI's arlo.m, which the toolbox's r2star_arlo is), 0 outside the mask. QSM.rs sets
# negative rates to 0, where the toolbox keeps them.
WORK="$(mktemp -d)"
qsmxt r2star "$IN/magnitude.nii.gz" -m "$IN/mask.nii.gz" -o "$WORK/r2star.nii.gz" --echo-times $TES
if [ -n "${QSMCI_INTERMEDIATES:-}" ]; then
  mkdir -p "$QSMCI_INTERMEDIATES"; cp "$WORK/r2star.nii.gz" "$QSMCI_INTERMEDIATES/r2star.nii.gz"
fi
qsmxt r2prime --r2star "$WORK/r2star.nii.gz" --r2primenet -m "$IN/mask.nii.gz" \
  -o "$OUT/r2prime.nii.gz" --field-strength "$FIELD" $SET
