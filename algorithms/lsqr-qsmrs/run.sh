#!/usr/bin/env bash
# QSM-CI submission — minimally regularised LSQR (dipole stage) via QSMxT / QSM.rs.
set -euo pipefail
IN="${1:-/input}"; OUT="${2:-/output}"
# Acquisition parameters are injected as env vars — no need to parse params.json/config.json:
#   $QSMCI_B0 (T)   $QSMCI_TE / $QSMCI_TE0 (s)   $QSMCI_B0_DIR   $QSMCI_VOXEL_SIZE (mm)
#   $QSMCI_SET_<NAME>  for each  qsm-ci run --set NAME=VALUE  override
B0=$(jq -r '.B0_dir | join(" ")' "$IN/params.json")
FIELD=$(jq -r .B0 "$IN/params.json")   # field strength (T); sets the default residual weighting

# LSQR takes the local field in ppm and returns χ in ppm. Magnitude, when provided, is an SNR row
# weight (renormalised to unit mean inside the mask, so its units don't matter); without it the
# rows are weighted uniformly.
MAG=""; [ -f "$IN/magnitude.nii.gz" ] && MAG="--magnitude $IN/magnitude.nii.gz"

# Parameter overrides (qsm-ci run --set NAME=VALUE) arrive as /input/config.json. Absent -> qsm-core
# LsqrQsmParams defaults. residual_weighting is deliberately left unpassed when unset: qsm-core then
# scales it with field strength, which pinning a number here would silently defeat.
SET=""
CFG="$IN/config.json"
if [ -f "$CFG" ]; then
  V=$(jq -r '.residual_weighting // empty' "$CFG"); [ -n "$V" ] && SET="$SET --lsqr-residual-weighting $V"
  V=$(jq -r '.tol // empty' "$CFG");                [ -n "$V" ] && SET="$SET --lsqr-tol $V"
  V=$(jq -r '.max_iter // empty' "$CFG");           [ -n "$V" ] && SET="$SET --lsqr-max-iter $V"
  # `// empty` cannot be used for a boolean: jq's `//` treats `false` as absent, so an explicit
  # `global_offset=false` would be silently swallowed. Test the value instead.
  if jq -e '.global_offset == false' "$CFG" >/dev/null; then SET="$SET --no-lsqr-global-offset"; fi
fi

qsmxt invert lsqr "$IN/localfield.nii.gz" -m "$IN/mask.nii.gz" -o "$OUT/chimap.nii.gz" \
  --b0-direction $B0 --b0 "$FIELD" $MAG $SET
