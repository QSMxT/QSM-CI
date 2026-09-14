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

# Run the per-voxel fit SERIALLY. This is not a typo: qsm-core's decompose parallel path scales
# backwards — measured in this image on one machine (12568-voxel fit, 6 echoes, uniform cores at a
# constant 3.35 GHz), 1 thread 10.9 s, 4 threads 27.3 s, 8 threads 37.6 s, and at 42168 voxels 1
# thread 37.1 s vs 8 threads 205.9 s. The outputs are bit-identical at every thread count (max |Δ|
# = 0), and another rayon method in the same image (`separate hc-chisep`) speeds up normally
# (3.6 s → 1.4 s, 1 → 8 threads), so this is specific to decompose, not the environment. Serial is
# therefore both the fastest and the most predictable setting until the upstream loop is fixed;
# drop this line then. Overridable: RAYON_NUM_THREADS=8 bash run.sh.
export RAYON_NUM_THREADS="${RAYON_NUM_THREADS:-1}"

# Parameter overrides (qsm-ci run --set NAME=VALUE) arrive as /input/config.json; absent = defaults.
SET=""
CFG="$IN/config.json"
if [ -f "$CFG" ]; then
  V=$(jq -r '.n_inner // empty' "$CFG");     [ -n "$V" ] && SET="$SET --n-inner $V"
  V=$(jq -r '.chi_bound // empty' "$CFG");   [ -n "$V" ] && SET="$SET --chi-bound $V"
  V=$(jq -r '.max_lm_iter // empty' "$CFG"); [ -n "$V" ] && SET="$SET --max-lm-iter $V"
fi

# -o is a PREFIX: the CLI writes {prefix}_paramagnetic.nii, _diamagnetic.nii and _total.nii
# (uncompressed). Stage them in a scratch dir, then publish the two canonical artifacts gzipped.
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
qsmxt separate decompose \
  --qsm "$IN/chimap.nii.gz" -m "$IN/mask.nii.gz" -o "$WORK/dec" \
  --magnitude "$IN/magnitude.nii.gz" --echo-times "$TE" \
  --field-strength "$B0" --b0-direction $B0DIR $SET

# qsmxt already emits χ+ ≥ 0 and the diamagnetic map as the positive magnitude |χ−| (it negates
# qsm-core's signed χ− in commands/separate.rs::save_result), which is exactly the contract — so
# these are a straight gzip, no sign flip. _total.nii (the signed net) is not a stage artifact.
gzip -c "$WORK/dec_paramagnetic.nii" > "$OUT/chi-para.nii.gz"
gzip -c "$WORK/dec_diamagnetic.nii" > "$OUT/chi-dia.nii.gz"
