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
# Env:   OSF_TOKEN     (required unless OSF_ZIP is set) — OSF personal access token
#        OSF_PROJECT   (default y8adf), OSF_FILE (default the bids.zip file id)
#        OSF_FILE_INVIVO (invivo track) — OSF file id of the pre-flattened invivo_qsm2016.zip
#        OSF_ZIP       (optional) — persistent path for the download. If it exists it's reused (no
#                      download); if not, the download is saved there. Point CI's cache at it.
#
# Tracks: sim / chisep ship as qsm-forward BIDS trees (flattened here by pack_dataset.py). The
# invivo track (2016 QSM Reconstruction Challenge) ships ALREADY FLATTENED (inputs/ + groundtruth/
# at the zip root, built by scripts/make_invivo_zip.py), so it skips the BIDS-find + pack step and
# just unzips straight into $DEST.
set -euo pipefail

TRACK="${1:?track required}"
DEST="${2:?dest dir required}"
OSF_PROJECT="${OSF_PROJECT:-y8adf}"
# bids.zip file id per track. The χ-separation phantom is a SEPARATE bids (χ+/χ− sources + R2'
# derivatives), so it lives in its own OSF file — set OSF_FILE_CHISEP (or override OSF_FILE).
case "$TRACK" in
  chisep) OSF_FILE="${OSF_FILE:-${OSF_FILE_CHISEP:?set OSF_FILE_CHISEP to the χ-sep bids.zip OSF file id}}"; PACK_FLAGS="--chisep" ;;
  invivo) OSF_FILE="${OSF_FILE:-${OSF_FILE_INVIVO:-hw9rn}}"; PACK_FLAGS="" ;;   # invivo_qsm2016.zip (osf.io/hw9rn), pre-flattened
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

# The invivo zip is ALREADY flattened (inputs/ + groundtruth/ at its root, built by
# scripts/make_invivo_zip.py) — no BIDS tree, no pack step. Just unzip it straight into $DEST.
if [ "$TRACK" = "invivo" ]; then
  rm -rf "$DEST"
  mkdir -p "$DEST"
  unzip -q "$zip" -d "$DEST"
  echo "[fetch_dataset] ${TRACK} dataset ready at ${DEST} (pre-flattened, no BIDS pack)"
  exit 0
fi

unzip -q "$zip" -d "$tmp/extract"
# Locate the BIDS root (the dir holding sub-*/anat with raw MEGRE, not the derivatives copy).
phase="$(find "$tmp/extract" -path '*/sub-*/anat/*part-phase_MEGRE.nii*' ! -path '*derivatives*' | head -1)"
[ -n "$phase" ] || { echo "[fetch_dataset] could not find raw phase under the zip" >&2; exit 1; }
bids="$(dirname "$(dirname "$(dirname "$phase")")")"

python3 "$SCRIPT_DIR/pack_dataset.py" "$bids" "$DEST" $PACK_FLAGS
echo "[fetch_dataset] ${TRACK} dataset ready at ${DEST}"
