#!/usr/bin/env bash
# Fetch held-out ground truth for a track from OSF into a destination dir.
# Mirrors the QSM.rs CI pattern (authenticated OSF download). Requires $OSF_TOKEN.
#
# Usage: fetch_groundtruth.sh <track> <dest-dir>
set -euo pipefail

TRACK="${1:?track required}"
DEST="${2:?dest dir required}"
: "${OSF_TOKEN:?OSF_TOKEN must be set}"

# TODO: fill in the QSM-CI OSF project id and file paths once the phantom is uploaded.
OSF_PROJECT="${OSF_PROJECT:-CHANG_ME}"
BASE="https://files.osf.io/v1/resources/${OSF_PROJECT}/providers/osfstorage"

mkdir -p "$DEST"
for f in chimap dseg; do
  echo "[fetch_groundtruth] downloading ${TRACK}/${f}.nii.gz"
  curl -fSL -H "Authorization: Bearer ${OSF_TOKEN}" \
    "${BASE}/${TRACK}/groundtruth/${f}.nii.gz" -o "${DEST}/${f}.nii.gz"
done
