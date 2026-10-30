#!/usr/bin/env bash
# QSM-CI submission — MEDI's complex fit (field-mapping stage) via QSMxT / QSM.rs.
#   consumes phase.nii.gz, magnitude.nii.gz, mask.nii.gz, params.json -> produces totalfield.nii.gz
# The total field is the complex fit unwrapped by ROMEO (MEDI's region-growing unwrapPhase is not
# ported), so it is not like for like with fit-ppm-complex-cornell's. With $QSMCI_INTERMEDIATES
# set, this also writes what is: the fit before unwrapping (ifreq_raw, radians per echo spacing,
# wrapped), its noise map (n_std, radians per echo spacing), both in MEDI's units and sign, and
# ARLO's R2* (r2star, Hz; 3+ echoes), as fit-ppm-complex-cornell's recon.m names them.
set -euo pipefail
IN="${1:-/input}"; OUT="${2:-/output}"

SET=""
CFG="$IN/config.json"
if [ -f "$CFG" ]; then
  V=$(jq -r '.reltol // empty' "$CFG"); [ -n "$V" ] && SET="$SET --complex-fit-reltol $V"
  V=$(jq -r '.max_iter // empty' "$CFG"); [ -n "$V" ] && SET="$SET --complex-fit-max-iter $V"
fi

INTER=""
if [ -n "${QSMCI_INTERMEDIATES:-}" ]; then
  INTER="$(mktemp -d)"
  SET="$SET --complex-fit-output $INTER/ifreq_raw.nii --complex-fit-noise-output $INTER/n_std.nii"
fi
qsmxt fieldmap romeo "$IN/phase.nii.gz" \
  -m "$IN/mask.nii.gz" \
  --magnitude "$IN/magnitude.nii.gz" \
  --params "$IN/params.json" \
  --b0-estimation complex-fit $SET \
  -o "$OUT/totalfield.nii.gz"

if [ -n "$INTER" ]; then
  TES=$(jq -r '.TE | map(tostring) | join(" ")' "$IN/params.json")
  if [ "$(jq '.TE | length' "$IN/params.json")" -ge 3 ]; then
    # shellcheck disable=SC2086
    qsmxt r2star "$IN/magnitude.nii.gz" -m "$IN/mask.nii.gz" -o "$INTER/r2star.nii" --echo-times $TES
  fi
  mkdir -p "$QSMCI_INTERMEDIATES"
  for f in "$INTER"/*.nii; do gzip -c "$f" > "$QSMCI_INTERMEDIATES/$(basename "$f").gz"; done
fi
