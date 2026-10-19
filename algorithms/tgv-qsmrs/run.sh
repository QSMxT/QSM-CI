#!/usr/bin/env bash
# QSM-CI submission — TGV (bfr+dipole stage) via QSMxT / QSM.rs.
set -euo pipefail
IN="${1:-/input}"; OUT="${2:-/output}"
B0=$(jq -r '.B0_dir | join(" ")' "$IN/params.json")

# Units: since qsmxt v10.0.0, `qsmxt invert tgv` takes the field in ppm (QSM-CI's totalfield
# contract) and writes χ in ppm, with no --echo-time / --field-strength. Its α are in ppm too, so a
# value means the same at every TE and field strength. (Before v10 the command expected a phase in
# radians and this script passed a dummy TE·B0 with 2π·γ·TE·B0 = 1 so a ppm field passed straight
# through; α given here were therefore already ppm-valued, and an override from that era means the
# same thing now.)
#
# REGULARIZATION DEFAULT: QSMxT's own (QSM.rs TgvParams::default — α1 = 0.0005 / 7.49 = 6.675e-5 ppm,
# α0 = 0.0015 / 7.49 = 2.002e-4 ppm: the Langkammer/nipype rad-domain α at the 7 T / 4 ms reference).
# Earlier QSM-CI releases passed α1 = 0.0005, α0 = 0.0015 here, because the bare default of the time
# (α = 0.001 in these units) over-smoothed; the v10 default is weaker than both, so that reason no
# longer applies and no α is passed unless overridden.

# Parameter overrides (qsm-ci run --set NAME=VALUE) arrive as /input/config.json.
SET=""
CFG="$IN/config.json"
if [ -f "$CFG" ]; then
  V=$(jq -r '.iterations // empty' "$CFG"); [ -n "$V" ] && SET="$SET --iterations $V"
  V=$(jq -r '.alpha1 // empty' "$CFG"); [ -n "$V" ] && SET="$SET --alpha1 $V"
  V=$(jq -r '.alpha0 // empty' "$CFG"); [ -n "$V" ] && SET="$SET --alpha0 $V"
fi
qsmxt invert tgv "$IN/totalfield.nii.gz" -m "$IN/mask.nii.gz" -o "$OUT/chimap.nii.gz" --b0-direction $B0 $SET
