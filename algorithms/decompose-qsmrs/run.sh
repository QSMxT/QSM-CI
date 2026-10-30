#!/usr/bin/env bash
# QSM-CI submission — DECOMPOSE-QSM (chi-separation stage) via QSMxT / QSM.rs.
#   consumes chimap.nii.gz (χ_total, ppm), magnitude.nii.gz (4D multi-echo), mask.nii.gz, params.json
#   produces chi-para.nii.gz (χ+ ≥ 0, ppm), chi-dia.nii.gz (|χ−| ≥ 0, ppm)
set -euo pipefail
IN="${1:-/input}"; OUT="${2:-/output}"
# Acquisition parameters are also injected as env vars ($QSMCI_B0, $QSMCI_TE, $QSMCI_B0_DIR, …), but
# params.json is parsed here so `bash run.sh` works outside the QSM-CI runner too.
B0="$(jq -r .B0 "$IN/params.json")"
B0DIR="$(jq -r '.B0_dir | join(" ")' "$IN/params.json")"
TE="$(jq -r '.TE | join(",")' "$IN/params.json")"   # seconds; the 4D magnitude's echo dim must match

# The per-voxel fit uses every core (rayon's default; RAYON_NUM_THREADS caps it). It used to be
# pinned to one thread here because qsm-core's DECOMPOSE loop allocated per voxel and the static
# musl allocator serialised that, so it got slower with threads. QSM.rs#93 made the loop
# allocation-free; since then it scales and gives bit-identical outputs at any thread count.

# Parameter overrides (qsm-ci run --set NAME=VALUE) arrive as /input/config.json; absent = defaults.
SET=""
CFG="$IN/config.json"
if [ -f "$CFG" ]; then
  V=$(jq -r '.n_inner // empty' "$CFG");     [ -n "$V" ] && SET="$SET --n-inner $V"
  V=$(jq -r '.chi_bound // empty' "$CFG");   [ -n "$V" ] && SET="$SET --chi-bound $V"
  V=$(jq -r '.max_lm_iter // empty' "$CFG"); [ -n "$V" ] && SET="$SET --max-lm-iter $V"
fi

# -o is a PREFIX: the CLI writes {prefix}_desc-paramagnetic_Chimap.nii, _desc-diamagnetic_Chimap.nii
# and _desc-total_Chimap.nii (uncompressed; the pipeline's BIDS names since qsmxt v10.0.0). Stage them in a scratch dir, then publish the two canonical artifacts gzipped.
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
# A qsmxt on QSM.rs#333 or later takes a QSM per echo (--qsm-per-echo). Like decompose-qsm, QSM-CI
# gives the one provided χ_total at every echo. Older releases (v10.0.0) take --qsm alone.
PER_ECHO=""
if qsmxt separate decompose --help 2>/dev/null | grep -q -- '--qsm-per-echo'; then
  NE="$(jq -r '.TE | length' "$IN/params.json")"
  PER_ECHO="--qsm-per-echo$(for _ in $(seq "$NE"); do printf ' %s' "$IN/chimap.nii.gz"; done)"
fi
qsmxt separate decompose \
  --qsm "$IN/chimap.nii.gz" -m "$IN/mask.nii.gz" -o "$WORK/dec" \
  --magnitude "$IN/magnitude.nii.gz" --echo-times "$TE" $PER_ECHO \
  --field-strength "$B0" --b0-direction $B0DIR $SET

# qsmxt already emits χ+ ≥ 0 and the diamagnetic map as the positive magnitude |χ−| (it negates
# qsm-core's signed χ− in commands/separate.rs::save_result), which is exactly the contract — so
# these are a straight gzip, no sign flip. The total map (the signed net) is not a stage artifact.
gzip -c "$WORK/dec_desc-paramagnetic_Chimap.nii" > "$OUT/chi-para.nii.gz"
gzip -c "$WORK/dec_desc-diamagnetic_Chimap.nii" > "$OUT/chi-dia.nii.gz"
