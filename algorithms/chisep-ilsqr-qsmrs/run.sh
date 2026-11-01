#!/usr/bin/env bash
# QSM-CI submission: χ-separation (iLSQR) via QSMxT / QSM.rs, the port of the SNU χ-separation
# toolbox's chi_sep_iLSQR (`chisep-ilsqr` runs the toolbox itself).
#   consumes localfield.nii.gz (ppm), r2prime.nii.gz (Hz), mask.nii.gz, params.json, and
#            chimap.nii.gz (χ_total, ppm) with qsm=chimap
#   produces chi-para.nii.gz (χ+ ≥ 0, ppm), chi-dia.nii.gz (|χ−| ≥ 0, ppm)
# As `chisep-ilsqr` (and the toolbox's Chisep_script.m), chi_sep_iLSQR starts from a QSM made with
# iLSQR from the local field (QSM.rs's port of STI Suite's QSM_iLSQR, 12 mm padding: the
# wrapper's 12 voxels on 1 mm data), not from chimap. qsm=chimap uses the given χ instead (the
# parity pair feeds it the original's own QSM, so only chi_sep_iLSQR is compared).
set -euo pipefail
IN="${1:-/input}"; OUT="${2:-/output}"
B0="$(jq -r .B0 "$IN/params.json")"
B0DIR="$(jq -r '.B0_dir | join(" ")' "$IN/params.json")"

SET=""
GAMMA=42.576     # MHz/T: qsmxt's γ (QSM.rs constants::GAMMA_BAR_HZ_PER_T), so CF = γ·B0
QSM=ilsqr
PAD_MM=12
CFG="$IN/config.json"
if [ -f "$CFG" ]; then
  V=$(jq -r '.gamma // empty' "$CFG");  [ -n "$V" ] && GAMMA="$V"
  V=$(jq -r '.qsm // empty' "$CFG");    [ -n "$V" ] && QSM="$V"
  V=$(jq -r '.pad_mm // empty' "$CFG"); [ -n "$V" ] && PAD_MM="$V"
fi
# CF = 42.576 MHz/T · B0 sets R2′'s ppm scale and the default D_r = 137·B0/2.9; another γ (the
# `chisep-ilsqr` wrapper's 42.5774) is applied by scaling the field strength qsmxt is given.
FS=$(awk -v b="$B0" -v g="$GAMMA" 'BEGIN { printf "%.17g", b * g / 42.576 }')

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
case "$QSM" in
  ilsqr)
    qsmxt invert ilsqr "$IN/localfield.nii.gz" -m "$IN/mask.nii.gz" -o "$WORK/qsm.nii.gz" \
      --b0-direction $B0DIR --pad-mm "$PAD_MM"
    CHI="$WORK/qsm.nii.gz" ;;
  chimap) CHI="$IN/chimap.nii.gz" ;;
  *) echo "chisep-ilsqr-qsmrs: qsm must be ilsqr or chimap" >&2; exit 1 ;;
esac
qsmxt separate chi-sep-ilsqr \
  --qsm "$CHI" -m "$IN/mask.nii.gz" --local-field "$IN/localfield.nii.gz" \
  --r2prime "$IN/r2prime.nii.gz" --field-strength "$FS" --b0-direction $B0DIR \
  -o "$WORK/cs" $SET
gzip -c "$WORK/cs_desc-paramagnetic_Chimap.nii" > "$OUT/chi-para.nii.gz"
gzip -c "$WORK/cs_desc-diamagnetic_Chimap.nii" > "$OUT/chi-dia.nii.gz"
