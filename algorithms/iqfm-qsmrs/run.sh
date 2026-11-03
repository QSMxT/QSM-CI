#!/usr/bin/env bash
# QSM-CI submission: iQFM (unwrap+bfr: wrapped phase → local field) via QSMxT / QSM.rs, the port of `iqfm`.
set -euo pipefail
IN="${1:-/input}"; OUT="${2:-/output}"

# Field strength (T), every echo time (s) and the B0 direction from params.json (QSMCI_* env,
# CONTRACT.md). The phase is every echo's wrapped phase in radians (4-D), as the original takes it;
# the local field comes out in ppm.
B0DIR="${QSMCI_B0_DIR:-$(jq -r '.B0_dir | join(" ")' "$IN/params.json")}"
FIELD="${QSMCI_B0:-$(jq -r .B0 "$IN/params.json")}"
TES="${QSMCI_TE:-$(jq -r '.TE | if type=="array" then map(tostring) | join(" ") else tostring end' "$IN/params.json")}"
MAG=""; [ -f "$IN/magnitude.nii.gz" ] && MAG="--magnitude $IN/magnitude.nii.gz"

# The echo weighting defaults to (magnitude × TE)², as the authors' Python code (run.py) that the
# `iqfm` entry runs. `--set echo_weighting=mag-te2` gives their MATLAB code's magnitude × TE².
SET=""
CFG="$IN/config.json"
if [ -f "$CFG" ]; then
  V=$(jq -r '.echo_weighting // empty' "$CFG"); [ -n "$V" ] && SET="$SET --echo-weighting $V"
fi
qsmxt bgremove iqfm "$IN/phase.nii.gz" -m "$IN/mask.nii.gz" -o "$OUT/localfield.nii.gz" \
  --field-strength "$FIELD" --echo-times $TES --b0-direction $B0DIR $MAG $SET
