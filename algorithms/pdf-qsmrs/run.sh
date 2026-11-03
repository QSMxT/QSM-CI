#!/usr/bin/env bash
# QSM-CI submission — PDF (bfr stage) via QSMxT / QSM.rs.
set -euo pipefail
IN="${1:-/input}"; OUT="${2:-/output}"
# Acquisition parameters are injected as env vars — no need to parse params.json/config.json:
#   $QSMCI_B0 (T)   $QSMCI_TE / $QSMCI_TE0 (s)   $QSMCI_B0_DIR   $QSMCI_VOXEL_SIZE (mm)
#   $QSMCI_SET_<NAME>  for each  qsm-ci run --set NAME=VALUE  override
B0=$(jq -r '.B0_dir | join(" ")' "$IN/params.json")

# Parameter overrides (qsm-ci run --set NAME=VALUE) arrive as /input/config.json.
SET=""
CFG="$IN/config.json"
if [ -f "$CFG" ]; then
  V=$(jq -r '.tol // empty' "$CFG"); [ -n "$V" ] && SET="$SET --tol $V"
  # PDF.m's other settings (qsmxt after v10.0.0; v10.0.0 refuses them)
  V=$(jq -r '.n_cg // empty' "$CFG"); [ -n "$V" ] && SET="$SET --n-cg $V"
  V=$(jq -r '.space // empty' "$CFG"); [ -n "$V" ] && SET="$SET --space $V"
  V=$(jq -r '.n_pad // empty' "$CFG"); [ -n "$V" ] && SET="$SET --n-pad $V"
fi
# QSMxT after v10.0.0 ports MEDI's PDF.m (astewartau/QSM.rs#257): it weights the fit by
# Fit_ppm_complex's noise map from every echo's magnitude, and needs the field strength and echo
# times to put that map in the field's units. qsmxt v10.0.0 takes none of them.
if qsmxt bgremove pdf --help 2>/dev/null | grep -q -- '--field-strength'; then
  FS=$(jq -r .B0 "$IN/params.json"); TES=$(jq -r '.TE | map(tostring) | join(" ")' "$IN/params.json")
  exec qsmxt bgremove pdf "$IN/totalfield.nii.gz" -m "$IN/mask.nii.gz" -o "$OUT/localfield.nii.gz" \
    --b0-direction $B0 --field-strength "$FS" --echo-times $TES --magnitude "$IN/magnitude.nii.gz" $SET
fi
qsmxt bgremove pdf "$IN/totalfield.nii.gz" -m "$IN/mask.nii.gz" -o "$OUT/localfield.nii.gz" --b0-direction $B0 $SET
