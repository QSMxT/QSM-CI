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
# Usage: fetch_dataset.sh <phantom> <dest>
#   <phantom> is a scripts/datasets.json registry key. The legacy track args (sim / invivo)
#   are themselves registry keys, so existing callers keep working identically.
# Env:   OSF_TOKEN     (required unless OSF_ZIP is set) — OSF personal access token
#        OSF_PROJECT   (default y8adf), OSF_FILE (overrides the registry's file id)
#        OSF_FILE_*    (per-phantom secrets) — the registry's `osf_env` names which one applies
#                      (e.g. OSF_FILE_CHISEP_MC for the chisep-mc phantom)
#        OSF_ZIP       (optional) — persistent path for the download. If it exists it's reused (no
#                      download); if not, the download is saved there. Point CI's cache at it.
#
# Phantoms shipping qsm-forward BIDS trees are flattened here by pack_dataset.py (with the registry's
# `pack_flags`, e.g. --chisep). A registry entry with `prepacked: true` (the 2016 invivo challenge
# zip, built by scripts/make_invivo_zip.py) ships ALREADY FLATTENED (inputs/ + groundtruth/ at the
# zip root), so it skips the BIDS-find + pack step and just unzips straight into $DEST.
set -euo pipefail

TRACK="${1:?phantom (scripts/datasets.json key) required}"
DEST="${2:?dest dir required}"
OSF_PROJECT="${OSF_PROJECT:-y8adf}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# Resolve the phantom in the dataset registry (scripts/datasets.json): its OSF file id (an explicit
# $OSF_FILE overrides everything; else the env secret named by the entry's `osf_env`; else the
# literal `osf_file`), its pack_dataset.py flags, and whether the zip is prepacked.
RESOLVED="$(python3 - "$TRACK" "$SCRIPT_DIR/datasets.json" <<'PY'
import json, os, sys
ph, regfile = sys.argv[1], sys.argv[2]
d = json.load(open(regfile)).get(ph)
if d is None:
    sys.exit(f"[fetch_dataset] unknown phantom '{ph}' — add it to scripts/datasets.json")
osf = os.environ.get("OSF_FILE") or (os.environ.get(d["osf_env"]) if d.get("osf_env") else None) \
      or d.get("osf_file")
if not osf:
    sys.exit(f"[fetch_dataset] no OSF file id for phantom '{ph}' — "
             f"set {d.get('osf_env', 'OSF_FILE')} (or OSF_FILE)")
print(f"OSF_FILE={osf}")
print(f"PACK_FLAGS={d.get('pack_flags', '')}")
print(f"PREPACKED={'1' if d.get('prepacked') else '0'}")
print(f"PUBLIC={'1' if d.get('osf_public') else '0'}")
# A registry entry may live in a different OSF project than the default (e.g. the public
# harmonization project); the OSF_PROJECT env still overrides.
if d.get("osf_project") and not os.environ.get("OSF_PROJECT"):
    print(f"OSF_PROJECT={d['osf_project']}")
PY
)"
eval "$RESOLVED"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

zip="${OSF_ZIP:-$tmp/bids.zip}"
if [ -f "$zip" ]; then
  echo "[fetch_dataset] using cached zip $zip"
else
  # A public project (e.g. the harmonization dataset) needs no token; a private one (the QSM.rs
  # reference data) does. Only require OSF_TOKEN when the registry entry isn't flagged public.
  if [ "${PUBLIC:-0}" != "1" ]; then
    : "${OSF_TOKEN:?OSF_TOKEN must be set (or provide an existing OSF_ZIP)}"
  fi
  echo "[fetch_dataset] downloading ${OSF_PROJECT}/${OSF_FILE} from OSF"
  mkdir -p "$(dirname "$zip")"
  # A 24-hex string is a waterbutler file id (osfstorage path); anything shorter is a file GUID,
  # downloaded via osf.io/<guid>/download. Both authenticate with the OSF token for a private project.
  # A PUBLIC project's file id downloads tokenless via osf.io/download/<id>/ (the bare waterbutler
  # URL only 302-redirects and then 400s without auth, so use the public download endpoint instead).
  if [ "${PUBLIC:-0}" = "1" ] && [[ "$OSF_FILE" =~ ^[0-9a-f]{24}$ ]]; then
    url="https://osf.io/download/${OSF_FILE}/"
  elif [[ "$OSF_FILE" =~ ^[0-9a-f]{24}$ ]]; then
    url="https://files.osf.io/v1/resources/${OSF_PROJECT}/providers/osfstorage/${OSF_FILE}"
  else
    url="https://osf.io/${OSF_FILE}/download"
  fi
  # --location-trusted: a GUID download redirects osf.io -> files.osf.io (-> signed storage); keep the
  # OSF token across those hops so a private-project file still authenticates. (Harmless for the direct
  # waterbutler URL, and the signed storage URL just ignores the extra header.) Send the auth header
  # ONLY when a token is set — an empty `Authorization: Bearer ` header makes OSF 400 the public
  # download endpoint, so a tokenless public fetch must omit it entirely.
  if [ -n "${OSF_TOKEN:-}" ]; then
    curl -fS --location-trusted -H "Authorization: Bearer ${OSF_TOKEN}" "$url" -o "$zip"
  else
    curl -fS --location-trusted "$url" -o "$zip"
  fi
fi

# A prepacked zip (registry `prepacked: true`, e.g. the invivo challenge) is ALREADY flattened
# (inputs/ + groundtruth/ at its root) — no BIDS tree, no pack step. Unzip it straight into $DEST.
if [ "$PREPACKED" = "1" ]; then
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
