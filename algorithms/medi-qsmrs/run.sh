#!/usr/bin/env bash
# QSM-CI submission — MEDI (dipole stage) via QSMxT / QSM.rs.
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
  V=$(jq -r '.lambda // empty' "$CFG"); [ -n "$V" ] && SET="$SET --lambda $V"
fi
FS=$(jq -r .B0 "$IN/params.json")
# QSMxT after v10.0.0 (QSM.rs main, run by the parity workflow's qsmxt builds) has MEDI_L1's own
# defaults (λ 1000, SMV 5 mm, MERIT, the CSF zero reference from the echo magnitudes), matching
# medi-cornell. It is given every echo time and runs with those defaults; λ is then on MEDI's
# scale, so a `--set lambda` from the pinned v10 (λ 1e-3 scale) does not carry over. The pinned
# v10.0.0 keeps the call below it was scored with.
if qsmxt invert medi --help 2>/dev/null | grep -q -- '--echo-times'; then
  TES=$(jq -r '.TE | map(tostring) | join(" ")' "$IN/params.json")
  exec qsmxt invert medi "$IN/localfield.nii.gz" -m "$IN/mask.nii.gz" -o "$OUT/chimap.nii.gz" \
    --b0-direction $B0 --field-strength "$FS" --echo-times $TES --magnitude "$IN/magnitude.nii.gz" $SET
fi
qsmxt invert medi "$IN/localfield.nii.gz" -m "$IN/mask.nii.gz" -o "$OUT/chimap.nii.gz" --b0-direction $B0 --field-strength "$FS" --echo-time "$(jq -r .TE[0] "$IN/params.json")" --smv false --magnitude "$IN/magnitude.nii.gz" $SET
