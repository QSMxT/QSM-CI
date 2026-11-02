#!/usr/bin/env bash
# QSM-CI submission: iQSM+ (end-to-end: wrapped phase → χ) via QSMxT / QSM.rs, the port of `iqsm-plus`.
set -euo pipefail
IN="${1:-/input}"; OUT="${2:-/output}"

# Field strength (T), every echo time (s) and the B0 direction from params.json (QSMCI_* env,
# CONTRACT.md). The phase is every echo's wrapped phase in radians (4-D), as the original takes it.
B0DIR="${QSMCI_B0_DIR:-$(jq -r '.B0_dir | join(" ")' "$IN/params.json")}"
FIELD="${QSMCI_B0:-$(jq -r .B0 "$IN/params.json")}"
TES="${QSMCI_TE:-$(jq -r '.TE | if type=="array" then map(tostring) | join(" ") else tostring end' "$IN/params.json")}"

# The echoes are combined with (magnitude × TE)² weights, as both of the authors' versions do; the
# network takes the B0 direction.
qsmxt invert iqsm-plus "$IN/phase.nii.gz" -m "$IN/mask.nii.gz" -o "$OUT/chimap.nii.gz" \
  --field-strength "$FIELD" --echo-times $TES --b0-direction $B0DIR --magnitude "$IN/magnitude.nii.gz"
