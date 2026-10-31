#!/usr/bin/env bash
# QSM-CI submission: WaveSep (chi-separation stage) via QSMxT / QSM.rs.
#   consumes chimap.nii.gz (χ_total, ppm), r2prime.nii.gz (Hz), mask.nii.gz, params.json
#   produces chi-para.nii.gz (χ+ ≥ 0, ppm), chi-dia.nii.gz (|χ−| ≥ 0, ppm)
set -euo pipefail
IN="${1:-/input}"; OUT="${2:-/output}"

# Parameter overrides (qsm-ci run --set NAME=VALUE) arrive as /input/config.json; absent = the
# defaults in algorithm.yml (the rest are qsmxt's, the authors').
# Dr: the published χ-separation value, 137 Hz/ppm at 3 T (Shin et al. 2021), scaled with field as the
# SNU χ-separation toolbox does (137·B0/2.9; QSM.rs chi_sep_ilsqr.rs `toolbox_default_dr`), the same
# default as the `wavesep` entry. WaveSep itself ships no value (it reads Dr per dataset).
# params.json is parsed here (not $QSMCI_B0) so `bash run.sh` works outside the QSM-CI runner too.
B0="$(jq -r '.B0 // empty' "$IN/params.json")"
[ -n "$B0" ] || { echo "wavesep-qsmrs: params.json has no B0 (the default Dr needs it)" >&2; exit 1; }
DR=$(awk -v b0="$B0" 'BEGIN { printf "%.10g", 137 * b0 / 2.9 }')
SET=""
CFG="$IN/config.json"
if [ -f "$CFG" ]; then
  V=$(jq -r '.Dr // empty' "$CFG");       [ -n "$V" ] && DR="$V"
  V=$(jq -r '.lambda // empty' "$CFG");   [ -n "$V" ] && SET="$SET --lambda $V"
  V=$(jq -r '.alpha // empty' "$CFG");    [ -n "$V" ] && SET="$SET --alpha $V"
  V=$(jq -r '.max_iter // empty' "$CFG"); [ -n "$V" ] && SET="$SET --max-iter $V"
fi

# -o is a PREFIX: qsmxt writes {prefix}_desc-paramagnetic_Chimap.nii and _desc-diamagnetic_ (the
# positive magnitude |χ−|, as the contract wants) uncompressed; publish the two gzipped.
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
qsmxt separate wavesep \
  --qsm "$IN/chimap.nii.gz" -m "$IN/mask.nii.gz" --r2prime "$IN/r2prime.nii.gz" \
  -o "$WORK/ws" --dr-pos "$DR" --dr-neg "$DR" $SET
gzip -c "$WORK/ws_desc-paramagnetic_Chimap.nii" > "$OUT/chi-para.nii.gz"
gzip -c "$WORK/ws_desc-diamagnetic_Chimap.nii" > "$OUT/chi-dia.nii.gz"
