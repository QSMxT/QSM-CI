#!/usr/bin/env bash
# Fetch a scoring dataset into <dest>/{inputs,groundtruth}.
#
#   inputs/       public boundary artifacts (phase, magnitude, mask, params.json)
#   groundtruth/  held-out targets + isolated-mode input boundaries (totalfield, localfield,
#                 chimap, dseg) — pulled from OSF with $OSF_TOKEN, never committed.
#
# Usage: fetch_dataset.sh <track> <dest>
set -euo pipefail

TRACK="${1:?track required}"
DEST="${2:?dest dir required}"
: "${OSF_TOKEN:?OSF_TOKEN must be set}"

# TODO: fill in the QSM-CI OSF project id (and whether inputs are public or also token-gated).
OSF_PROJECT="${OSF_PROJECT:-CHANG_ME}"
BASE="https://files.osf.io/v1/resources/${OSF_PROJECT}/providers/osfstorage/${TRACK}"

fetch() { # <remote-subpath> <local-path>
  mkdir -p "$(dirname "$2")"
  curl -fSL -H "Authorization: Bearer ${OSF_TOKEN}" "${BASE}/$1" -o "$2"
}

for f in phase.nii.gz magnitude.nii.gz mask.nii.gz params.json; do
  fetch "inputs/$f" "${DEST}/inputs/$f"
done
for f in totalfield.nii.gz localfield.nii.gz chimap.nii.gz dseg.nii.gz; do
  fetch "groundtruth/$f" "${DEST}/groundtruth/$f"
done

echo "[fetch_dataset] populated ${DEST}"
