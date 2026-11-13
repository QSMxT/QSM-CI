#!/usr/bin/env bash
# Fetch a scoring dataset into <dest>/{inputs,groundtruth}.
#
# Source of truth is the QSM.rs reference BIDS on OSF (private project y8adf, "QSM Rust Test Data"):
# a single bids.zip with raw multi-echo data + derivatives/qsm-forward ground truth. This downloads
# it (token-gated), unpacks, and flattens it into the QSM-CI artifact layout via pack_dataset.py.
#
#   inputs/       public boundary artifacts (phase, magnitude, mask, params.json)
#   groundtruth/  scoring targets + isolated-mode input boundaries (totalfield, localfield,
#                 chimap, dseg) — never committed.
#
# Usage: fetch_dataset.sh <phantom> <dest>
#   <phantom> is a scripts/datasets.json registry key. The legacy track args (sim / invivo)
#   are themselves registry keys, so existing callers keep working identically.
# Env:   OSF_TOKEN     OSF personal access token (read scope is enough). Required for a private
#                      project unless OSF_ZIP is set; optional for an `osf_public` one, which then
#                      downloads authenticated, so it keeps working if that project is made private.
#        HF_TOKEN      Hugging Face token. An entry with `hf_repo`/`hf_path` (a private HF dataset copy)
#                      is downloaded from there first when it is set, with OSF as the fallback.
#        OSF_PROJECT   (default y8adf), OSF_FILE (overrides the registry's file id, and with it
#                      the registry's `osf_version`)
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
# `osf_version` pins one OSF version of the registry's file: OSF serves the LATEST version by default,
# and a file id can gain new versions that other consumers rely on (the MGH pilot ids carry the
# original packs as their latest version for `qsmxt example`, and the re-masked packs QSM-CI scores as
# version 2). It belongs to the registry's file, so an $OSF_FILE / `osf_env` override drops it.
ver = d.get("osf_version") if osf == d.get("osf_file") and not os.environ.get("OSF_FILE") else None
print(f"OSF_VERSION={ver or ''}")
print(f"PACK_FLAGS={d.get('pack_flags', '')}")
print(f"PREPACKED={'1' if d.get('prepacked') else '0'}")
print(f"PUBLIC={'1' if d.get('osf_public') else '0'}")
# A registry entry may live in a different OSF project than the default (e.g. the public
# harmonization project); the OSF_PROJECT env still overrides.
if d.get("osf_project") and not os.environ.get("OSF_PROJECT"):
    print(f"OSF_PROJECT={d['osf_project']}")
# A private Hugging Face copy (registry `hf_repo` + `hf_path`) is tried first when HF_TOKEN is set;
# OSF stays the fallback. `sha256` (when given) is checked whichever source served the zip.
print(f"HF_REPO={d.get('hf_repo', '')}")
print(f"HF_PATH={d.get('hf_path', '')}")
print(f"SHA256={d.get('sha256', '')}")
PY
)"
eval "$RESOLVED"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

zip="${OSF_ZIP:-$tmp/bids.zip}"
if [ -f "$zip" ]; then
  echo "[fetch_dataset] using cached zip $zip"
else
  # Hugging Face first, for an entry that has a copy there and when a token is available. curl does
  # not forward a -H Authorization header to another host when it follows a redirect, so the token
  # goes to huggingface.co only, never to the CDN it redirects to.
  got=0
  if [ -n "${HF_REPO:-}" ] && [ -n "${HF_PATH:-}" ]; then
    if [ -n "${HF_TOKEN:-}" ]; then
      echo "[fetch_dataset] downloading ${HF_REPO}/${HF_PATH} from Hugging Face"
      mkdir -p "$(dirname "$zip")"
      code="$(curl -sSL -o "$zip" -w '%{http_code}' -H "Authorization: Bearer ${HF_TOKEN}" \
              "https://huggingface.co/datasets/${HF_REPO}/resolve/main/${HF_PATH}")" || code=000
      if [ "$code" = 200 ]; then
        got=1
      else
        rm -f "$zip"
        echo "[fetch_dataset] Hugging Face answered HTTP $code for ${HF_REPO}/${HF_PATH} (a 401/404 means" \
             "HF_TOKEN cannot read this private dataset); falling back to OSF" >&2
      fi
    else
      echo "[fetch_dataset] no HF_TOKEN: skipping the Hugging Face copy (${HF_REPO}); trying OSF" >&2
    fi
  fi
  if [ "$got" != 1 ]; then
    # A public project (e.g. the harmonization dataset) needs no token; a private one (the QSM.rs
    # reference data) does. Only require OSF_TOKEN when the registry entry isn't flagged public.
    if [ "${PUBLIC:-0}" != "1" ] && [ -z "${OSF_TOKEN:-}" ]; then
      echo "[fetch_dataset] ${TRACK} is in a private OSF project (${OSF_PROJECT}): set OSF_TOKEN to an OSF" \
           "personal access token with read access (in CI: pass secrets.OSF_TOKEN)${HF_REPO:+, or HF_TOKEN for its Hugging Face copy ${HF_REPO}}," \
           "or provide an existing OSF_ZIP" >&2
      exit 1
    fi
    echo "[fetch_dataset] downloading ${OSF_PROJECT}/${OSF_FILE} from OSF"
    mkdir -p "$(dirname "$zip")"
    # A 24-hex string is a waterbutler file id (osfstorage path); anything shorter is a file GUID,
    # downloaded via osf.io/<guid>/download. Both authenticate with the OSF token for a private project.
    # A PUBLIC project's file id downloads tokenless via osf.io/download/<id>/ (the bare waterbutler
    # URL only 302-redirects and then 400s without auth, so use the public download endpoint instead).
    # With a token, a 24-hex id always goes through the authenticated WaterButler URL, public project
    # or not: it works for both, so flipping a public project to private needs no registry change as
    # long as CI passes OSF_TOKEN.
    if [ "${PUBLIC:-0}" = "1" ] && [ -z "${OSF_TOKEN:-}" ] && [[ "$OSF_FILE" =~ ^[0-9a-f]{24}$ ]]; then
      url="https://osf.io/download/${OSF_FILE}/"
    elif [[ "$OSF_FILE" =~ ^[0-9a-f]{24}$ ]]; then
      url="https://files.osf.io/v1/resources/${OSF_PROJECT}/providers/osfstorage/${OSF_FILE}"
    else
      url="https://osf.io/${OSF_FILE}/download"
    fi
    # All three endpoints take `?version=N` (a registry `osf_version`); without it OSF serves the latest.
    if [ -n "${OSF_VERSION:-}" ]; then
      [[ "$OSF_VERSION" =~ ^[0-9]+$ ]] || { echo "[fetch_dataset] bad osf_version '$OSF_VERSION' for ${TRACK}" >&2; exit 1; }
      url="${url}?version=${OSF_VERSION}"
      echo "[fetch_dataset] pinned to OSF version ${OSF_VERSION}"
    fi
    # A GUID download redirects osf.io -> files.osf.io -> a pre-signed object-storage URL. The OSF
    # token must reach the OSF hops of a private project, but the storage host rejects a signed URL
    # that also carries an Authorization header (HTTP 400), so follow the redirects by hand and send
    # the token only to *.osf.io. Send no auth header at all without a token: an empty
    # `Authorization: Bearer ` header makes OSF 400 the public download endpoint.
    hop="$url"
    for _ in 1 2 3 4 5 6 7 8; do
      auth=()
      if [ -n "${OSF_TOKEN:-}" ] && [[ "$hop" =~ ^https://([a-z0-9-]+\.)*osf\.io/ ]]; then
        auth=(-H "Authorization: Bearer ${OSF_TOKEN}")
      fi
      # A redirect's small body is overwritten by the next hop; the last hop's body is the file.
      # -f would hide the status, so check it ourselves: a 401/403/404 from OSF on a tokenless
      # download is what a project that has been made private looks like.
      out="$(curl -sS -o "$zip" -w '%{http_code} %{redirect_url}' "${auth[@]}" "$hop")" || {
        echo "[fetch_dataset] download failed: $url" >&2; rm -f "$zip"; exit 1; }
      code="${out%% *}"; next="${out#* }"
      if [ "$code" -ge 400 ]; then
        rm -f "$zip"
        if [ -z "${OSF_TOKEN:-}" ] && { [ "$code" = 401 ] || [ "$code" = 403 ] || [ "$code" = 404 ] || [ "$code" = 410 ]; }; then
          echo "[fetch_dataset] HTTP $code downloading ${OSF_PROJECT}/${OSF_FILE} without a token: the OSF" \
               "project is probably private now. Set OSF_TOKEN (an OSF token with read access; in CI" \
               "pass secrets.OSF_TOKEN to this step)." >&2
        elif [ "$code" = 401 ] || [ "$code" = 403 ]; then
          echo "[fetch_dataset] HTTP $code downloading ${OSF_PROJECT}/${OSF_FILE}: OSF_TOKEN was sent but" \
               "has no read access to this project (wrong account, expired, or missing a read scope)." >&2
        else
          echo "[fetch_dataset] HTTP $code downloading ${OSF_PROJECT}/${OSF_FILE} from $hop" >&2
        fi
        exit 1
      fi
      # An anonymous request for a private project's file is not refused with a 4xx: OSF redirects it
      # to its sign-in page (which would then download as a 200 HTML "zip"). Stop there instead.
      if [[ "$next" =~ ^https://accounts\.osf\.io/ ]]; then
        rm -f "$zip"
        echo "[fetch_dataset] OSF redirected ${OSF_PROJECT}/${OSF_FILE} to its sign-in page: the project is" \
             "private and ${OSF_TOKEN:+the OSF_TOKEN sent has no read access to it}${OSF_TOKEN:-no OSF_TOKEN was set}." \
             "Set OSF_TOKEN to an OSF token with read access (in CI: pass secrets.OSF_TOKEN to this step)." >&2
        exit 1
      fi
      hop="$next"
      [ -n "$hop" ] || break
    done
    [ -z "$hop" ] || { echo "[fetch_dataset] too many redirects from $url" >&2; exit 1; }
  fi
  if [ -n "${SHA256:-}" ]; then
    have="$(sha256sum "$zip" | cut -d' ' -f1)"
    if [ "$have" != "$SHA256" ]; then
      rm -f "$zip"
      echo "[fetch_dataset] sha256 mismatch for ${TRACK}: expected ${SHA256}, got ${have}" >&2
      exit 1
    fi
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
# The parent of its sub-* directory: not a fixed number of levels up, since a subject may have a
# ses-* level, and which subject `find` returns first differs between filesystems.
rel="/${phase#"$tmp/extract/"}"
bids="$tmp/extract${rel%%/sub-*}"

python3 "$SCRIPT_DIR/pack_dataset.py" "$bids" "$DEST" $PACK_FLAGS
echo "[fetch_dataset] ${TRACK} dataset ready at ${DEST}"
