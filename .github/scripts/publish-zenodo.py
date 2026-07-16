#!/usr/bin/env python3
"""Publish QSM-CI method submissions to Zenodo and maintain the version registry.

Each ``algorithms/<slug>/`` folder is a citable, versioned artifact. For every method this script:

* pins the container ``image:`` to an immutable ``@sha256`` digest (so a version reproduces exactly);
* zips the git-tracked method files and checksums the zip;
* skips the method when that (slug, version) already published the same checksum;
* otherwise creates a new Zenodo deposition (first time — a stable **concept DOI**) or a **new
  version** of the existing record (a fresh, immutable **version DOI**), uploads the zip, and publishes;
* records everything in ``qsm_ci/registry.json`` keyed ``slug → {concept_doi, latest, versions:
  {<version>: {version_doi, record_id, checksum}}}`` — the mapping the CLI ships and resolves against.

The method version is the ``version:`` field in ``algorithm.yml`` (default ``1.0``). Bump it when you
change a method; reusing a version with different content is refused so a version DOI is always a
fixed artifact. Adapted from dicompare-web's publish-zenodo.py.
"""

import argparse
import datetime
import hashlib
import io
import os
import re
import subprocess
import sys
import zipfile

import yaml

from urllib import error as urlerror
from urllib import request as urlrequest
import json

KEYWORDS = ["QSM", "quantitative susceptibility mapping", "MRI", "reconstruction", "QSM-CI"]


def log(m): print(m, flush=True)
def warn(m): print(f"WARNING: {m}", file=sys.stderr, flush=True)


def api(url, token, method="GET", data=None, headers=None, expect_json=True):
    h = {"Authorization": f"Bearer {token}"}
    body = None
    if isinstance(data, (bytes, bytearray)):
        body = data
    elif data is not None:
        body = json.dumps(data).encode(); h["Content-Type"] = "application/json"
    if headers:
        h.update(headers)
    req = urlrequest.Request(url, data=body, method=method, headers=h)
    try:
        with urlrequest.urlopen(req) as r:
            payload = r.read()
    except urlerror.HTTPError as e:
        raise RuntimeError(f"{method} {url} failed ({e.code}): {e.read().decode('utf-8','replace')}") from e
    return json.loads(payload.decode()) if expect_json and payload else ({} if expect_json else payload)


# --- method packaging --------------------------------------------------------------------------

def image_digest(ref):
    """Resolve a tag to its immutable digest via docker (best-effort)."""
    for cmd in (["docker", "buildx", "imagetools", "inspect", ref, "--format", "{{.Manifest.Digest}}"],
                ["docker", "manifest", "inspect", "--verbose", ref]):
        try:
            out = subprocess.run(cmd, capture_output=True, text=True)
        except FileNotFoundError:
            return None
        if out.returncode == 0:
            m = re.search(r"sha256:[0-9a-f]{64}", out.stdout)
            if m:
                return m.group(0)
    return None


def pin_image(algorithm_yml_text):
    """Rewrite `image: repo:tag` → `image: repo@sha256:…`. Returns (text, pinned_ref_or_None)."""
    m = re.search(r"^image:\s*(\S+)\s*$", algorithm_yml_text, re.M)
    if not m:
        return algorithm_yml_text, None
    ref = m.group(1)
    if "@sha256:" in ref:
        return algorithm_yml_text, ref
    repo = ref.rsplit(":", 1)[0] if ":" in ref.rsplit("/", 1)[-1] else ref
    digest = image_digest(ref)
    if not digest:
        return algorithm_yml_text, None
    pinned = f"{repo}@{digest}"
    return algorithm_yml_text.replace(f"image: {ref}", f"image: {pinned}"), pinned


def method_zip(slug, algo_dir):
    """Zip the git-tracked files of a method, with its image digest-pinned. Returns (bytes, pinned)."""
    listed = subprocess.run(["git", "ls-files", algo_dir], capture_output=True, text=True, check=True)
    files = [f for f in listed.stdout.splitlines() if f.strip()]
    if not any(f.endswith("algorithm.yml") for f in files):
        raise RuntimeError(f"{slug}: no tracked algorithm.yml under {algo_dir}")
    pinned = None
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(files):
            arcname = os.path.relpath(f, os.path.dirname(algo_dir.rstrip("/")))  # <slug>/<file>
            text = open(f, "rb").read()
            if f.endswith("algorithm.yml"):
                new, pinned = pin_image(text.decode())
                text = new.encode()
            # Deterministic entry: a fixed timestamp + mode so an unchanged method yields a
            # STABLE checksum across runs. Otherwise writestr(arcname, ...) stamps the current
            # time into the zip, the checksum differs every run, the "skip if unchanged" guard
            # never fires, and every publish re-mints a Zenodo version DOI for all 26 methods.
            info = zipfile.ZipInfo(arcname, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            z.writestr(info, text)
    return buf.getvalue(), pinned


def checksum(blob):
    return "sha256:" + hashlib.sha256(blob).hexdigest()


# --- Zenodo deposition -------------------------------------------------------------------------

def draft(base, token, prev_record_id):
    if prev_record_id:
        res = api(f"{base}/api/deposit/depositions/{prev_record_id}/actions/newversion", token, "POST")
        dep = api(res["links"]["latest_draft"], token)
        for f in dep.get("files", []):
            if f.get("id"):
                api(f"{base}/api/deposit/depositions/{dep['id']}/files/{f['id']}", token, "DELETE", expect_json=False)
        return dep
    return api(f"{base}/api/deposit/depositions", token, "POST", data={})


def upload(base, token, dep, blob, filename):
    bucket = dep.get("links", {}).get("bucket")
    if not bucket:
        raise RuntimeError("deposition has no bucket link")
    api(f"{bucket}/{filename}", token, "PUT", data=blob, headers={"Content-Type": "application/octet-stream"})


def metadata(meta, slug, version, site_base):
    authors = [a.get("name") for a in (meta.get("authors") or []) if a.get("name")] or ["QSM-CI"]
    page = f"{site_base}/leaderboard.html?method={slug}"
    desc = (f"{meta.get('description') or ''}<br><br>"
            f"QSM-CI reconstruction method <code>{slug}</code>. "
            f'Browse and run it at <a href="{page}">{page}</a>.')
    related = [{"identifier": page, "relation": "isDocumentedBy", "scheme": "url"}]
    if meta.get("code_url") and meta["code_url"] != "null":
        related.append({"identifier": meta["code_url"], "relation": "isSupplementTo", "scheme": "url"})
    if meta.get("doi") and meta["doi"] != "null":
        related.append({"identifier": str(meta["doi"]), "relation": "cites", "scheme": "doi"})
    return {"metadata": {
        "title": f"QSM-CI method: {meta.get('name') or slug} (v{version})",
        "upload_type": "software", "description": desc, "creators": [{"name": a} for a in authors],
        "version": str(version), "keywords": KEYWORDS, "related_identifiers": related,
        "license": _license_id(meta.get("license")),
    }}


# Zenodo validates `license` against a controlled vocabulary. Map to a valid id, and fall back to
# `other-closed` for restrictive/custom licenses (e.g. "See STI Suite License") that aren't open ids.
_VALID_LICENSES = {
    "mit", "apache-2.0", "bsd-2-clause", "bsd-3-clause", "gpl-2.0", "gpl-3.0", "lgpl-2.1", "lgpl-3.0",
    "agpl-3.0", "mpl-2.0", "isc", "unlicense", "cc0-1.0", "cc-by-4.0", "cc-by-sa-4.0", "cc-by-nc-4.0",
    "other-open", "other-closed", "other-pd",
}


def _license_id(raw) -> str:
    lic = str(raw or "MIT").strip().lower().replace(" ", "-")
    return lic if lic in _VALID_LICENSES else "other-closed"


def publish(base, site_base, token, slug, meta, version, blob, prev_record_id):
    dep = draft(base, token, prev_record_id)
    upload(base, token, dep, blob, f"{slug}.zip")
    api(f"{base}/api/deposit/depositions/{dep['id']}", token, "PUT", data=metadata(meta, slug, version, site_base))
    pub = api(f"{base}/api/deposit/depositions/{dep['id']}/actions/publish", token, "POST")
    m = pub.get("metadata", {})
    return {
        "version_doi": m.get("doi") or pub.get("doi"),
        "record_id": str(pub.get("record_id") or pub.get("id")),
        "concept_doi": m.get("conceptdoi") or pub.get("conceptdoi"),
        "concept_recid": str(pub.get("conceptrecid")) if pub.get("conceptrecid") else None,
        "zenodo_url": pub.get("links", {}).get("record_html") or pub.get("links", {}).get("html"),
    }


# --- discovery + main --------------------------------------------------------------------------

def discover(algorithms_dir):
    out = []
    for name in sorted(os.listdir(algorithms_dir)):
        d = os.path.join(algorithms_dir, name)
        yml = os.path.join(d, "algorithm.yml")
        if name.startswith("_") or not os.path.isfile(yml):
            continue
        meta = yaml.safe_load(open(yml)) or {}
        out.append((meta.get("slug") or name, d, meta))
    return out


def main():
    p = argparse.ArgumentParser(description="Publish QSM-CI methods to Zenodo.")
    p.add_argument("--algorithms-dir", default="algorithms")
    p.add_argument("--mapping", default="qsm_ci/registry.json")
    p.add_argument("--zenodo-token", default=os.environ.get("ZENODO_TOKEN"))
    p.add_argument("--zenodo-base-url", default="https://sandbox.zenodo.org")
    p.add_argument("--site-base-url", default="https://qsmxt.github.io/QSM-CI")
    p.add_argument("--only", help="publish just this slug")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    if not args.zenodo_token and not args.dry_run:
        p.error("A Zenodo token is required (--zenodo-token or ZENODO_TOKEN).")

    base = args.zenodo_base_url.rstrip("/")
    mapping = json.load(open(args.mapping)) if os.path.exists(args.mapping) else {}
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    published = skipped = failures = 0

    for slug, algo_dir, meta in discover(args.algorithms_dir):
        if args.only and slug != args.only:
            continue
        try:
            blob, pinned = method_zip(slug, algo_dir)
        except Exception as e:  # noqa: BLE001
            warn(f"{slug}: cannot package: {e}"); failures += 1; continue
        ck = checksum(blob)
        entry = mapping.get(slug, {"versions": {}})
        versions = entry.get("versions", {})

        # Unchanged since the last publish → skip. Otherwise the version is publish-assigned: the
        # next integer, which we also set as Zenodo's version metadata (so they never drift).
        if versions and versions.get(entry.get("latest"), {}).get("checksum") == ck:
            log(f"{slug} v{entry['latest']}: unchanged, skipping"); skipped += 1; continue
        version = str(max((int(k) for k in versions), default=0) + 1)

        if not pinned:
            # Refuse to mint a DOI for a non-reproducible method — a digest is the whole point.
            warn(f"{slug}: could not resolve its image to a digest (bad image ref, or docker "
                 f"unavailable) — skipping. A published version must be byte-reproducible.")
            failures += 1
            continue
        if args.dry_run:
            log(f"{slug} v{version}: would {'create' if not entry.get('versions') else 'add version'} "
                f"(image={pinned or 'UNPINNED'}, {ck[:20]}…)"); published += 1; continue

        try:
            prev = versions.get(entry.get("latest"), {}).get("record_id") if entry.get("latest") else None
            res = publish(base, args.site_base_url, args.zenodo_token, slug, meta, version, blob, prev)
            versions[version] = {"version_doi": res["version_doi"], "record_id": res["record_id"],
                                 "checksum": ck, "image": pinned, "updated_at": now}
            entry["versions"] = versions
            entry["latest"] = version
            entry["concept_doi"] = res.get("concept_doi") or entry.get("concept_doi")
            entry["concept_recid"] = res.get("concept_recid") or entry.get("concept_recid")
            mapping[slug] = entry
            published += 1
            log(f"{slug} v{version}: {res['version_doi']} (concept {entry['concept_doi']})")
        except Exception as e:  # noqa: BLE001
            warn(f"{slug}: publish failed: {e}"); failures += 1

    if not args.dry_run:
        json.dump(mapping, open(args.mapping, "w"), indent=2, sort_keys=True)
        open(args.mapping, "a").write("\n")

    log(f"Done. published={published} skipped={skipped} failures={failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
