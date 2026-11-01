#!/usr/bin/env bash
# QSM-CI submission — DECOMPOSE-QSM (chi-separation stage) via QSMxT / QSM.rs.
#   consumes chimap.nii.gz (χ_total, ppm), magnitude.nii.gz (4D multi-echo), mask.nii.gz, params.json,
#            and chimap-echoes.nii.gz (χ(TE), 4D, ppm) when the dataset ships it
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
  # `// empty` would drop a JSON false, so read unwrap_phase by key.
  V=$(jq -r 'if has("unwrap_phase") then .unwrap_phase | tostring else empty end' "$CFG")
  [ -n "$V" ] && SET="$SET --unwrap-phase $V"
fi

# -o is a PREFIX: the CLI writes {prefix}_desc-paramagnetic_Chimap.nii, _desc-diamagnetic_Chimap.nii
# and _desc-total_Chimap.nii (uncompressed; the pipeline's BIDS names since qsmxt v10.0.0). Stage them in a scratch dir, then publish the two canonical artifacts gzipped.
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
# DECOMPOSE takes a QSM per echo, χ(TE): the apparent susceptibility each echo's phase gives
# (Chen et al. 2021, Eq. 4; §4.1 calls it necessary). Its echo dependence is what the fit separates,
# so the one echo-independent chimap repeated at every echo leaves it nothing to fit.
#  - The dataset ships chimap-echoes (x,y,z,echo, ppm; CONTRACT.md): pass it, one 4D file.
#  - It doesn't: fall back to chimap at every echo, as before.
# A qsmxt on QSM.rs#333 or later takes --qsm-per-echo; older releases (v10.0.0, the pinned image)
# take --qsm alone and cannot use chimap-echoes (logged).
PER_ECHO=""
if qsmxt separate decompose --help 2>/dev/null | grep -q -- '--qsm-per-echo'; then
  if [ -f "$IN/chimap-echoes.nii.gz" ]; then
    PER_ECHO="--qsm-per-echo $IN/chimap-echoes.nii.gz"
  else
    NE="$(jq -r '.TE | length' "$IN/params.json")"
    PER_ECHO="--qsm-per-echo$(for _ in $(seq "$NE"); do printf ' %s' "$IN/chimap.nii.gz"; done)"
  fi
elif [ -f "$IN/chimap-echoes.nii.gz" ]; then
  echo "decompose-qsmrs: this qsmxt has no --qsm-per-echo; chimap-echoes is ignored" >&2
fi
# At 7 T, QSMxT's rules decompose.unwrap-7t and decompose.chi-bound-7t (QSM.rs#345, from 6.5 T)
# suggest unwrapping along the echoes and the echo-spacing χ bound; QSMxT users get them by
# accepting the suggestion. QSM-CI scores the method as QSMxT runs it, so this entry applies them
# at 7 T. Below 6.5 T it runs the defaults (the authors' code: no unwrapping, 0.5 ppm bound). A
# --set chi_bound / --set unwrap_phase overrides each suggestion; parity sets both to the authors'
# defaults, as the MATLAB reference runs (parity/thresholds.yml). A qsmxt without --unwrap-phase
# (v10.0.0) is left as it is.
SUGGESTED=""
if awk -v b="$B0" 'BEGIN{exit !(b >= 6.5)}' && qsmxt separate decompose --help 2>/dev/null | grep -q -- '--unwrap-phase'; then
  case " $SET " in *" --unwrap-phase "*) ;; *) SUGGESTED="--unwrap-phase true" ;; esac
  case " $SET " in *" --chi-bound "*) ;; *) SUGGESTED="$SUGGESTED --chi-bound echo-spacing" ;; esac
fi
qsmxt separate decompose \
  --qsm "$IN/chimap.nii.gz" -m "$IN/mask.nii.gz" -o "$WORK/dec" \
  --magnitude "$IN/magnitude.nii.gz" --echo-times "$TE" $PER_ECHO \
  --field-strength "$B0" --b0-direction $B0DIR $SUGGESTED $SET

# qsmxt already emits χ+ ≥ 0 and the diamagnetic map as the positive magnitude |χ−| (it negates
# qsm-core's signed χ− in commands/separate.rs::save_result), which is exactly the contract — so
# these are a straight gzip, no sign flip. The total map (the signed net) is not a stage artifact.
gzip -c "$WORK/dec_desc-paramagnetic_Chimap.nii" > "$OUT/chi-para.nii.gz"
gzip -c "$WORK/dec_desc-diamagnetic_Chimap.nii" > "$OUT/chi-dia.nii.gz"
