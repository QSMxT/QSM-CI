#!/usr/bin/env bash
# QSM-CI submission: χ-separation (MEDI) via QSMxT / QSM.rs, the port of the SNU χ-separation
# toolbox's chi_sep_MEDI (`chisep-medi` runs the toolbox itself).
#   consumes localfield.nii.gz (ppm), r2prime.nii.gz (Hz), chimap.nii.gz (χ_total, ppm),
#            magnitude.nii.gz (x, y, z, echo), mask.nii.gz, params.json
#   produces chi-para.nii.gz (χ+ ≥ 0, ppm), chi-dia.nii.gz (|χ−| ≥ 0, ppm)
# The same inputs as `chisep-medi`: χ_total is the initial guess, N_std is MEDI Fit_ppm_complex's
# noise map from the echoes' magnitudes and the magnitude edges come from their root-sum-of-squares
# (qsmxt computes both), and there is no CSF term, since the stage contract has no CSF mask
# (`chisep-medi` passes mask_CSF = []).
set -euo pipefail
IN="${1:-/input}"; OUT="${2:-/output}"
B0="$(jq -r .B0 "$IN/params.json")"
B0DIR="$(jq -r '.B0_dir | join(" ")' "$IN/params.json")"
TE="$(jq -r '.TE | join(",")' "$IN/params.json")"   # seconds; the 4D magnitude's echo dim must match

# Parameter overrides (qsm-ci run --set NAME=VALUE) arrive as /input/config.json; absent = the
# defaults in algorithm.yml (the rest are qsmxt's, the toolbox's).
SET=""
GAMMA=42.576     # MHz/T: qsmxt's γ (QSM.rs constants::GAMMA_BAR_HZ_PER_T), so CF = γ·B0
CSF=none
CFG="$IN/config.json"
if [ -f "$CFG" ]; then
  V=$(jq -r '.lambda // empty' "$CFG");   [ -n "$V" ] && SET="$SET --lambda $V"
  V=$(jq -r '.gamma // empty' "$CFG");    [ -n "$V" ] && GAMMA="$V"
  V=$(jq -r '.csf_mask // empty' "$CFG"); [ -n "$V" ] && CSF="$V"
fi
# qsmxt takes the field strength and uses CF = 42.576 MHz/T · B0 for the field's Hz scale and the
# default D_r = 137·B0/2.9; another γ (the `chisep-medi` wrapper's 42.5774) is applied by scaling
# the field strength it is given.
FS=$(awk -v b="$B0" -v g="$GAMMA" 'BEGIN { printf "%.17g", b * g / 42.576 }')

case "$CSF" in
  none) CSF_ARG="--csf-mask none" ;;
  r2star) CSF_ARG="" ;;   # qsmxt's default: the CSF from ARLO R2* of the echoes, as Chisep_script.m
  *) echo "chisep-medi-qsmrs: csf_mask must be none or r2star" >&2; exit 1 ;;
esac

# -o is a PREFIX: qsmxt writes {prefix}_desc-paramagnetic_Chimap.nii and _desc-diamagnetic_ (the
# positive magnitude |χ−|, as the contract wants) uncompressed; publish the two gzipped.
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
qsmxt separate chi-sep-medi \
  --qsm "$IN/chimap.nii.gz" -m "$IN/mask.nii.gz" --local-field "$IN/localfield.nii.gz" \
  --r2prime "$IN/r2prime.nii.gz" --magnitude "$IN/magnitude.nii.gz" \
  --echo-times "$TE" --field-strength "$FS" --b0-direction $B0DIR -o "$WORK/cs" $CSF_ARG $SET
gzip -c "$WORK/cs_desc-paramagnetic_Chimap.nii" > "$OUT/chi-para.nii.gz"
gzip -c "$WORK/cs_desc-diamagnetic_Chimap.nii" > "$OUT/chi-dia.nii.gz"
