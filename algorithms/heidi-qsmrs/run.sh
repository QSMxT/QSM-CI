#!/usr/bin/env bash
# QSM-CI submission — HEIDI (dipole stage) via QSMxT / QSM.rs.
# Homogeneity Enabled Incremental Dipole Inversion: keeps the well-conditioned k-space of an LSQR
# seed and re-derives the dipole cone under a field-gradient-weighted TV prior (NESTA).
set -euo pipefail
IN="${1:-/input}"; OUT="${2:-/output}"
# Acquisition parameters are injected as env vars — no need to parse params.json/config.json:
#   $QSMCI_B0 (T)   $QSMCI_TE / $QSMCI_TE0 (s)   $QSMCI_B0_DIR   $QSMCI_VOXEL_SIZE (mm)
#   $QSMCI_SET_<NAME>  for each  qsm-ci run --set NAME=VALUE  override
B0=$(jq -r '.B0_dir | join(" ")' "$IN/params.json")
FIELD=$(jq -r .B0 "$IN/params.json")   # field strength (T); sets the LSQR seed's residual weighting
# Every echo time (s): HEIDI converts χ to the authors' phase units at the last one (qsm_heidi's
# phase2susceptibilityfactor.m), so its result depends on them.
TES=$(jq -r '.TE | map(tostring) | join(" ")' "$IN/params.json")

# HEIDI takes the local field in ppm and returns χ in ppm. Magnitude, when provided, is an SNR row
# weight for the LSQR seed — so it reaches the cone coefficients HEIDI keeps. The seed itself is run
# unmasked by qsmxt (HEIDI low-passes χ through the dipole cone, and a hard mask edge rings); that is
# not a flag here.
MAG=""; [ -f "$IN/magnitude.nii.gz" ] && MAG="--magnitude $IN/magnitude.nii.gz"

# Parameter overrides (qsm-ci run --set NAME=VALUE) arrive as /input/config.json. Absent -> qsm-core
# HeidiParams / LsqrQsmParams defaults. lsqr_residual_weighting is deliberately left unpassed when
# unset: qsm-core then scales it with field strength, which pinning a number here would defeat.
SET=""
CFG="$IN/config.json"
if [ -f "$CFG" ]; then
  V=$(jq -r '.cone_threshold // empty' "$CFG");         [ -n "$V" ] && SET="$SET --heidi-cone-threshold $V"
  V=$(jq -r '.gradient_threshold // empty' "$CFG");     [ -n "$V" ] && SET="$SET --heidi-gradient-threshold $V"
  V=$(jq -r '.gradient_mask_floor // empty' "$CFG");    [ -n "$V" ] && SET="$SET --heidi-gradient-mask-floor $V"
  V=$(jq -r '.continuation_steps // empty' "$CFG");     [ -n "$V" ] && SET="$SET --heidi-continuation-steps $V"
  V=$(jq -r '.inner_iterations // empty' "$CFG");       [ -n "$V" ] && SET="$SET --heidi-inner-iterations $V"
  V=$(jq -r '.tol // empty' "$CFG");                    [ -n "$V" ] && SET="$SET --heidi-tol $V"
  V=$(jq -r '.lsqr_residual_weighting // empty' "$CFG"); [ -n "$V" ] && SET="$SET --lsqr-residual-weighting $V"
  V=$(jq -r '.lsqr_max_iter // empty' "$CFG");          [ -n "$V" ] && SET="$SET --lsqr-max-iter $V"
  # A boolean: `// empty` would swallow false, so test the value.
  if jq -e '.denoise_reference_itk == true' "$CFG" >/dev/null; then SET="$SET --heidi-denoise-reference-itk"; fi
fi

# QSMxT main requires the field strength and echo times; the pinned v10.0.0 doesn't take them.
SCAN=""
if qsmxt invert heidi --help 2>/dev/null | grep -q -- '--field-strength'; then
  SCAN="--field-strength $FIELD --echo-times $TES"
fi
qsmxt invert heidi "$IN/localfield.nii.gz" -m "$IN/mask.nii.gz" -o "$OUT/chimap.nii.gz" \
  --b0-direction $B0 $SCAN $MAG $SET
