#!/usr/bin/env bash
# QSM-CI submission — AMP-PE (dipole stage) via QSMxT / QSM.rs.
# Approximate Message Passing with Parameter Estimation: nonlinear Bayesian dipole inversion.
set -euo pipefail
IN="${1:-/input}"; OUT="${2:-/output}"
# Acquisition parameters are injected as env vars — no need to parse params.json/config.json:
#   $QSMCI_B0 (T)   $QSMCI_TE / $QSMCI_TE0 (s)   $QSMCI_B0_DIR   $QSMCI_VOXEL_SIZE (mm)
#   $QSMCI_SET_<NAME>  for each  qsm-ci run --set NAME=VALUE  override
B0=$(jq -r '.B0_dir | join(" ")' "$IN/params.json")
FIELD=$(jq -r .B0 "$IN/params.json")   # field strength (T); scales the simulated phase

# AMP-PE takes the local field in ppm (like NDI). Magnitude, when provided, is the data-fidelity
# weight + wavelet morphology mask (a multi-echo 4D magnitude is RSS-combined); without it the
# method runs with uniform weights and no morphology mask. χ comes back in ppm.
MAG=""; [ -f "$IN/magnitude.nii.gz" ] && MAG="--magnitude $IN/magnitude.nii.gz"

# Parameter overrides (qsm-ci run --set NAME=VALUE) arrive as /input/config.json. Absent -> qsm-core
# AmpPeParams defaults (tuning-free by design; the noise/signal parameters are estimated internally).
SET=""
CFG="$IN/config.json"
if [ -f "$CFG" ]; then
  V=$(jq -r '.wave_order // empty' "$CFG");             [ -n "$V" ] && SET="$SET --wave-order $V"
  V=$(jq -r '.nlevel // empty' "$CFG");                 [ -n "$V" ] && SET="$SET --nlevel $V"
  V=$(jq -r '.wave_pec // empty' "$CFG");               [ -n "$V" ] && SET="$SET --wave-pec $V"
  V=$(jq -r '.simulated_te // empty' "$CFG");           [ -n "$V" ] && SET="$SET --simulated-te $V"
  V=$(jq -r '.max_linearization_ite // empty' "$CFG");  [ -n "$V" ] && SET="$SET --max-linearization-ite $V"
  V=$(jq -r '.damp_rate_sig // empty' "$CFG");          [ -n "$V" ] && SET="$SET --damp-rate-sig $V"
  V=$(jq -r '.damp_rate_par // empty' "$CFG");          [ -n "$V" ] && SET="$SET --damp-rate-par $V"
fi

qsmxt invert amp-pe "$IN/localfield.nii.gz" -m "$IN/mask.nii.gz" -o "$OUT/chimap.nii.gz" \
  --b0-direction $B0 --b0 "$FIELD" $MAG $SET
