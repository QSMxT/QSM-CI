#!/usr/bin/env bash
# QSM-CI submission — MEDI's complex fit (field-mapping stage) via QSMxT / QSM.rs.
#   consumes phase.nii.gz, magnitude.nii.gz, mask.nii.gz, params.json -> produces totalfield.nii.gz
# The total field is the complex fit unwrapped by config.json's `unwrapping`: ROMEO (the default),
# or MEDI's region growing (`medi-region-growing`, QSM.rs's port of unwrapPhase), which makes it
# like for like with fit-ppm-complex-cornell's (the parity pair runs that). With $QSMCI_INTERMEDIATES
# set, this also writes the fit before unwrapping (ifreq_raw, radians per echo spacing,
# wrapped), its noise map (n_std, radians per echo spacing), both in MEDI's units and sign, and
# ARLO's R2* (r2star, Hz; 3+ echoes), as fit-ppm-complex-cornell's recon.m names them.
set -euo pipefail
IN="${1:-/input}"; OUT="${2:-/output}"

SET=""
UNWRAP=romeo
CFG="$IN/config.json"
if [ -f "$CFG" ]; then
  V=$(jq -r '.unwrapping // empty' "$CFG"); [ -n "$V" ] && UNWRAP="$V"
  case "$UNWRAP" in romeo|medi-region-growing) ;; *) echo "unwrapping: '$UNWRAP' is not romeo or medi-region-growing" >&2; exit 2 ;; esac
  V=$(jq -r '.reltol // empty' "$CFG"); [ -n "$V" ] && SET="$SET --complex-fit-reltol $V"
  V=$(jq -r '.max_iter // empty' "$CFG"); [ -n "$V" ] && SET="$SET --complex-fit-max-iter $V"
fi

INTER=""
if [ -n "${QSMCI_INTERMEDIATES:-}" ]; then
  INTER="$(mktemp -d)"
  # --complex-fit-output/--complex-fit-noise-output: QSMxT/QSMxT#462, after v10.0.0 (which has no
  # --b0-estimation complex-fit at all). A qsmxt without them still writes r2star.
  if qsmxt fieldmap "$UNWRAP" --help 2>/dev/null | grep -q -- '--complex-fit-output'; then
    SET="$SET --complex-fit-output $INTER/ifreq_raw.nii --complex-fit-noise-output $INTER/n_std.nii"
  else
    echo "fit-ppm-complex-qsmrs: this qsmxt has no --complex-fit-output; ifreq_raw/n_std not written" >&2
  fi
fi
# MEDI's region growing takes no mask (it grows over the whole volume, as unwrapPhase does);
# qsmxt uses the mask only after it.
qsmxt fieldmap "$UNWRAP" "$IN/phase.nii.gz" \
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
  shopt -s nullglob
  for f in "$INTER"/*.nii; do gzip -c "$f" > "$QSMCI_INTERMEDIATES/$(basename "$f").gz"; done
fi
