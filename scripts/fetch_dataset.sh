#!/usr/bin/env bash
# Fetch a scoring dataset into <dest>/{inputs,groundtruth}.
#
# Source of truth is the QSM.rs reference BIDS on OSF (private project y8adf, "QSM Rust Test Data"):
# a single bids.zip with raw multi-echo data + derivatives/qsm-forward ground truth. This downloads
# it (token-gated), unpacks, and flattens it into the QSM-CI artifact layout via pack_dataset.py.
#
#   inputs/       public boundary artifacts (phase, magnitude, mask, params.json)
#   groundtruth/  held-out targets + isolated-mode input boundaries (totalfield, localfield,
#                 chimap, dseg) — never committed.
#
# Usage: fetch_dataset.sh <track> <dest>
# Env:   OSF_TOKEN   (required unless OSF_ZIP is set) — OSF personal access token
#        OSF_PROJECT (default y8adf), OSF_FILE (default the bids.zip file id)
#        OSF_ZIP     (optional) — persistent path for bids.zip. If it exists it's reused (no
#                    download); if not, the download is saved there. Point CI's cache at it.
set -euo pipefail

TRACK="${1:?track required}"
DEST="${2:?dest dir required}"
OSF_PROJECT="${OSF_PROJECT:-y8adf}"
# bids.zip file id per track. The χ-separation phantom is a SEPARATE bids (χ+/χ− sources + R2'
# derivatives), so it lives in its own OSF file — set OSF_FILE_CHISEP (or override OSF_FILE).
case "$TRACK" in
  chisep) OSF_FILE="${OSF_FILE:-${OSF_FILE_CHISEP:?set OSF_FILE_CHISEP to the χ-sep bids.zip OSF file id}}"; PACK_FLAGS="--chisep" ;;
  *)      OSF_FILE="${OSF_FILE:-698ac9aecae88916d1e24f69}"; PACK_FLAGS="" ;;   # QSM bids
esac
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

zip="${OSF_ZIP:-$tmp/bids.zip}"
if [ -f "$zip" ]; then
  echo "[fetch_dataset] using cached zip $zip"
else
  : "${OSF_TOKEN:?OSF_TOKEN must be set (or provide an existing OSF_ZIP)}"
  echo "[fetch_dataset] downloading ${OSF_PROJECT}/${OSF_FILE} from OSF"
  mkdir -p "$(dirname "$zip")"
  # A 24-hex string is a waterbutler file id (osfstorage path); anything shorter is a file GUID,
  # downloaded via osf.io/<guid>/download. Both authenticate with the OSF token for a private project.
  if [[ "$OSF_FILE" =~ ^[0-9a-f]{24}$ ]]; then
    url="https://files.osf.io/v1/resources/${OSF_PROJECT}/providers/osfstorage/${OSF_FILE}"
  else
    url="https://osf.io/${OSF_FILE}/download"
  fi
  # --location-trusted: a GUID download redirects osf.io -> files.osf.io (-> signed storage); keep the
  # OSF token across those hops so a private-project file still authenticates. (Harmless for the direct
  # waterbutler URL, and the signed storage URL just ignores the extra header.)
  curl -fS --location-trusted -H "Authorization: Bearer ${OSF_TOKEN}" "$url" -o "$zip"
fi

unzip -q "$zip" -d "$tmp/extract"
# Locate the BIDS root (the dir holding sub-*/anat with raw MEGRE, not the derivatives copy).
phase="$(find "$tmp/extract" -path '*/sub-*/anat/*part-phase_MEGRE.nii*' ! -path '*derivatives*' | head -1)"
[ -n "$phase" ] || { echo "[fetch_dataset] could not find raw phase under the zip" >&2; exit 1; }
bids="$(dirname "$(dirname "$(dirname "$phase")")")"

python3 "$SCRIPT_DIR/pack_dataset.py" "$bids" "$DEST" $PACK_FLAGS
echo "[fetch_dataset] ${TRACK} dataset ready at ${DEST}"
