#!/usr/bin/env bash
# QSM-CI submission — TFI (bfr+dipole stage) via QSMxT / QSM.rs.
# Preconditioned total field inversion: total field -> susceptibility, doing its own background removal.
set -euo pipefail
IN="${1:-/input}"; OUT="${2:-/output}"
# Acquisition parameters are injected as env vars — no need to parse params.json/config.json:
#   $QSMCI_B0 (T)   $QSMCI_TE / $QSMCI_TE0 (s)   $QSMCI_B0_DIR   $QSMCI_VOXEL_SIZE (mm)
#   $QSMCI_SET_<NAME>  for each  qsm-ci run --set NAME=VALUE  override
B0=$(jq -r '.B0_dir | join(" ")' "$IN/params.json")

# TFI takes the total field in ppm directly (like NDI — no radians conversion; the QSM-CI contract's
# totalfield is already ppm and `qsmxt invert tfi` consumes ppm). Magnitude (provided by the
# bfr+dipole stage) is used for the SNR data weight + morphology mask.
MAG=""; [ -f "$IN/magnitude.nii.gz" ] && MAG="--magnitude $IN/magnitude.nii.gz"

# Parameter overrides (qsm-ci run --set NAME=VALUE) arrive as /input/config.json. Absent -> qsm-core
# TfiParams defaults (lambda 7.5e-5, precond 30) — honest, non-dataset-tuned.
SET=""
CFG="$IN/config.json"
if [ -f "$CFG" ]; then
  V=$(jq -r '.lambda // empty' "$CFG");  [ -n "$V" ] && SET="$SET --lambda $V"
  V=$(jq -r '.precond // empty' "$CFG"); [ -n "$V" ] && SET="$SET --precond $V"
  # MEDI_L1's other settings (merit and linear are booleans: `// empty` would swallow false)
  V=$(jq -r 'if has("merit") then .merit | tostring else empty end' "$CFG"); [ -n "$V" ] && SET="$SET --merit $V"
  V=$(jq -r 'if has("linear") then .linear | tostring else empty end' "$CFG"); [ -n "$V" ] && SET="$SET --linear $V"
  V=$(jq -r '.data_weighting // empty' "$CFG"); [ -n "$V" ] && SET="$SET --data-weighting $V"
  V=$(jq -r '.percentage // empty' "$CFG"); [ -n "$V" ] && SET="$SET --percentage $V"
  V=$(jq -r '.cg_tol // empty' "$CFG"); [ -n "$V" ] && SET="$SET --cg-tol $V"
  V=$(jq -r '.cg_max_iter // empty' "$CFG"); [ -n "$V" ] && SET="$SET --cg-max-iter $V"
  V=$(jq -r '.max_iter // empty' "$CFG"); [ -n "$V" ] && SET="$SET --max-iter $V"
  V=$(jq -r '.tol // empty' "$CFG"); [ -n "$V" ] && SET="$SET --tol $V"
fi

# QSMxT after v10.0.0 runs TFI as the MEDI toolbox implements it (MEDI_L1 with a preconditioner,
# astewartau/QSM.rs#246): λ on MEDI's scale (default 1000), the field in radians over the echo
# spacing, every echo's magnitude required (edge mask and Fit_ppm_complex's noise weight). It needs
# the field strength and echo times; a `--set lambda` from the pinned v10.0.0 (λ 7.5e-5 scale) does
# not carry over. qsmxt v10.0.0 takes no scan parameters.
SCAN=""
if qsmxt invert tfi --help 2>/dev/null | grep -q -- '--field-strength'; then
  SCAN="--field-strength $(jq -r .B0 "$IN/params.json") --echo-times $(jq -r '.TE | map(tostring) | join(" ")' "$IN/params.json")"
fi
qsmxt invert tfi "$IN/totalfield.nii.gz" -m "$IN/mask.nii.gz" -o "$OUT/chimap.nii.gz" \
  --b0-direction $B0 $SCAN $MAG $SET
