#!/usr/bin/env bash
# QSM-CI submission: WaveSep (chi-separation stage) via QSMxT / QSM.rs.
#   consumes chimap.nii.gz (χ_total, ppm), r2prime.nii.gz (Hz), mask.nii.gz, params.json
#   produces chi-para.nii.gz (χ+ ≥ 0, ppm), chi-dia.nii.gz (|χ−| ≥ 0, ppm)
set -euo pipefail
IN="${1:-/input}"; OUT="${2:-/output}"

# Parameter overrides (qsm-ci run --set NAME=VALUE) arrive as /input/config.json; absent = the
# defaults in algorithm.yml (Dr 137, as the `wavesep` entry; the rest are qsmxt's, the authors').
DR=137.0
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
