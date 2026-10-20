#!/usr/bin/env bash
# QSM-CI submission — DECOMPOSE-QSM fitted to the measured complex signal (chi-separation stage)
# via QSMxT / QSM.rs.
#   consumes magnitude.nii.gz + phase.nii.gz (4D multi-echo; phase wrapped, whole-head, background
#            field included — all fine: the fit's free per-voxel φ0 and Δω absorb them), mask.nii.gz,
#            params.json
#   produces chi-para.nii.gz (χ+ ≥ 0, ppm), chi-dia.nii.gz (|χ−| ≥ 0, ppm)
set -euo pipefail
IN="${1:-/input}"; OUT="${2:-/output}"
B0="$(jq -r .B0 "$IN/params.json")"
B0DIR="$(jq -r '.B0_dir | join(" ")' "$IN/params.json")"
TE="$(jq -r '.TE | join(",")' "$IN/params.json")"   # seconds; must match the 4D echo dimension

# Parameter overrides (qsm-ci run --set NAME=VALUE) arrive as /input/config.json; absent = defaults.
SET=""
CFG="$IN/config.json"
if [ -f "$CFG" ]; then
  V=$(jq -r '.chi_bound // empty' "$CFG");   [ -n "$V" ] && SET="$SET --chi-bound $V"
  V=$(jq -r '.r2_bound // empty' "$CFG");    [ -n "$V" ] && SET="$SET --r2-bound $V"
  V=$(jq -r '.max_lm_iter // empty' "$CFG"); [ -n "$V" ] && SET="$SET --max-lm-iter $V"
fi

# -o is a PREFIX: the CLI writes {prefix}_desc-{paramagnetic,diamagnetic,total}_Chimap.nii.
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
qsmxt separate decompose-complex \
  --magnitude "$IN/magnitude.nii.gz" --phase "$IN/phase.nii.gz" --echo-times "$TE" \
  -m "$IN/mask.nii.gz" -o "$WORK/dcx" \
  --field-strength "$B0" --b0-direction $B0DIR $SET

# qsmxt writes χ+ ≥ 0 and the diamagnetic map as |χ−| already — the contract — so a straight gzip.
gzip -c "$WORK/dcx_desc-paramagnetic_Chimap.nii" > "$OUT/chi-para.nii.gz"
gzip -c "$WORK/dcx_desc-diamagnetic_Chimap.nii" > "$OUT/chi-dia.nii.gz"
