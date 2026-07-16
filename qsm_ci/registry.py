"""Resolve a method reference to a local algorithm folder, fetching versioned, DOI-citable
submissions from Zenodo when they aren't already in a local checkout.

A ``qsm-ci run <target>`` target may be:

- a slug — ``tkd`` — the newest published version in the shipped registry (:data:`registry.json`);
- a pinned version — ``tkd@1.2`` — that exact version;
- a Zenodo DOI/record — ``doi:10.5281/zenodo.123`` or ``10.5281/zenodo.123`` — fetched directly.

**Local checkouts always win** — a folder under ``./algorithms`` or ``$QSMCI_ALGORITHMS`` is used
as-is (no network), so development and submissions are unaffected. Only when a slug isn't found
locally do we consult the registry and fetch the method's files from Zenodo, caching them under
``$QSMCI_CACHE`` (default ``~/.cache/qsm-ci/methods/<record-id>/``).

Each Zenodo record is a self-contained method definition (``algorithm.yml`` + ``run.sh`` + recon),
with the container image pinned by digest — so a version DOI reproduces byte-for-byte, and every
submission gets a citable DOI. The registry is minted by ``.github/scripts/publish-zenodo.py``.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import urllib.request
import zipfile
from pathlib import Path

ZENODO_RECORD_API = "https://zenodo.org/api/records/{recid}"
_mapping_cache: "dict | None" = None


def _cache_root() -> Path:
    base = os.environ.get("QSMCI_CACHE") or os.path.join(os.path.expanduser("~"), ".cache", "qsm-ci")
    return Path(base) / "methods"


def load_mapping() -> dict:
    """The shipped slug → published-versions registry (``qsm_ci/registry.json``)."""
    global _mapping_cache
    if _mapping_cache is None:
        text = "{}"
        try:
            from importlib.resources import files
            text = (files("qsm_ci") / "registry.json").read_text() or "{}"
        except (FileNotFoundError, ModuleNotFoundError, OSError):
            pass
        _mapping_cache = json.loads(text)
    return _mapping_cache


def parse_target(target: str) -> "tuple[str, object]":
    """Classify a run target → ('recid', id) | ('version', (slug, ver)) | ('slug', slug)."""
    t = target.strip()
    if t.lower().startswith("doi:"):
        t = t[4:].strip()
    low = t.lower()
    # A Zenodo record URL — .../record/123 or .../records/123 — carries the id after 'record(s)/'.
    if "zenodo.org/record" in low:
        tail = low.split("record", 1)[1].lstrip("s").strip("/").split("/")[0].split("?")[0]
        if tail.isdigit():
            return "recid", tail
    # A Zenodo DOI — 10.5281/zenodo.123 — carries the id after 'zenodo.'.
    if "zenodo." in low:
        tail = low.split("zenodo.")[-1].strip("/").split("/")[0]
        if tail.isdigit():
            return "recid", tail
    if "@" in t and not t.startswith("."):
        slug, ver = t.split("@", 1)
        return "version", (slug, ver)
    return "slug", t


def _record_id(kind: str, value: object, mapping: dict) -> "str | None":
    if kind == "recid":
        return str(value)
    if kind == "slug":
        entry = mapping.get(value)
        if not entry:
            return None
        return entry["versions"][entry["latest"]]["record_id"]
    if kind == "version":
        slug, ver = value  # type: ignore[misc]
        entry = mapping.get(slug)
        if not entry or ver not in entry.get("versions", {}):
            return None
        return entry["versions"][ver]["record_id"]
    return None


def _expected_checksum(kind: str, value: object, mapping: dict) -> "str | None":
    """The sha256 of the method zip recorded in the registry (None for a raw DOI fetch)."""
    if kind == "slug":
        entry = mapping.get(value)
        return entry["versions"][entry["latest"]].get("checksum") if entry else None
    if kind == "version":
        slug, ver = value  # type: ignore[misc]
        entry = mapping.get(slug)
        return entry["versions"][ver].get("checksum") if entry and ver in entry.get("versions", {}) else None
    return None


def describe(target: str) -> "dict | None":
    """Registry metadata (concept/version DOI, etc.) for a target, for citation — None if unknown."""
    kind, value = parse_target(target)
    mapping = load_mapping()
    if kind == "slug":
        entry = mapping.get(value)
        if not entry:
            return None
        ver = entry["latest"]
        return {"slug": value, "version": ver, "concept_doi": entry.get("concept_doi"),
                **entry["versions"][ver]}
    if kind == "version":
        slug, ver = value  # type: ignore[misc]
        entry = mapping.get(slug)
        if not entry or ver not in entry.get("versions", {}):
            return None
        return {"slug": slug, "version": ver, "concept_doi": entry.get("concept_doi"),
                **entry["versions"][ver]}
    return None


def resolve(target: str, log=print) -> "Path | None":
    """Resolve a slug / slug@version / DOI to a cached local method folder. None if unknown."""
    kind, value = parse_target(target)
    mapping = load_mapping()
    recid = _record_id(kind, value, mapping)
    if recid is None:
        return None
    return _fetch_record(recid, _expected_checksum(kind, value, mapping), log)


def _fetch_record(recid: str, sha256: "str | None", log) -> Path:
    dest = _cache_root() / recid
    if (dest / "algorithm.yml").exists():
        return dest  # already cached

    log(f"  ↓ fetching method record {recid} from Zenodo")
    meta = json.loads(_http_bytes(ZENODO_RECORD_API.format(recid=recid)).decode())
    tmp = Path(tempfile.mkdtemp(prefix="qsm-ci-zenodo-"))
    try:
        extracted = tmp
        for f in meta.get("files", []):
            name = f["key"]
            blob = _http_bytes(f["links"]["self"])
            if name.endswith(".zip") and sha256:
                got = hashlib.sha256(blob).hexdigest()
                want = sha256.split(":", 1)[-1]
                if got != want:
                    raise RuntimeError(f"checksum mismatch for {name} (record {recid})")
            (tmp / name).write_bytes(blob)
            if name.endswith(".zip"):
                with zipfile.ZipFile(tmp / name) as z:
                    z.extractall(tmp / "unzipped")
                extracted = tmp / "unzipped"
        hits = list(extracted.rglob("algorithm.yml"))
        if not hits:
            raise RuntimeError(f"Zenodo record {recid} contains no algorithm.yml")
        src = hits[0].parent
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(src, dest)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return dest


def _http_bytes(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "qsm-ci"})
    with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310 (https only)
        return resp.read()
