"""qsm_ci/registry.py `_fetch_record` — fetching a method from Zenodo into the local cache.

Offline: `_http_bytes` is monkeypatched to serve a record built in memory. What is under test is the
cache contract, because the cache is code we later execute:

  * "cached" means `algorithm.yml` exists, so the cache must only ever be filled by an atomic
    rename — a `copytree` interrupted just after landing that one file left a permanently cached,
    half-copied method that every later run reused without re-fetching;
  * every file the record lists is verified, not only the `.zip`, and an UNVERIFIABLE file is
    refused rather than trusted.
"""
from __future__ import annotations

import hashlib
import io
import json
import zipfile

import pytest

from qsm_ci import registry

RECID = "424242"
ALGO_YML = b"slug: demo\nname: Demo\nstage: dipole\nimage: ghcr.io/x/y:v1\n"
RUN_SH = b"#!/bin/sh\npython3 /algo/recon.py \"$1\" \"$2\"\n"


def _zip_bytes(names_to_bodies: dict) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, body in names_to_bodies.items():
            z.writestr(name, body)
    return buf.getvalue()


def _record(files: dict) -> tuple[dict, dict]:
    """(record metadata as the Zenodo API returns it, {url: bytes})."""
    meta, blobs = {"files": []}, {}
    for name, body in files.items():
        url = f"https://zenodo.test/{name}"
        meta["files"].append({"key": name, "links": {"self": url},
                              "checksum": "md5:" + hashlib.md5(body).hexdigest()})
        blobs[url] = body
    return meta, blobs


@pytest.fixture
def serve(monkeypatch, tmp_path):
    """Point the cache at tmp_path and serve a record from memory. Returns a setup callable."""
    monkeypatch.setenv("QSMCI_CACHE", str(tmp_path / "cache"))

    def _setup(files, *, corrupt=None, drop_checksum=()):
        meta, blobs = _record(files)
        for entry in meta["files"]:
            if entry["key"] in drop_checksum:
                del entry["checksum"]
        def _http(url):
            if url.endswith(f"/{RECID}"):
                return json.dumps(meta).encode()
            body = blobs[url]
            return corrupt if corrupt is not None and url.endswith(".zip") else body
        monkeypatch.setattr(registry, "_http_bytes", _http)
        return meta
    return _setup


def _payload():
    return {"method.zip": _zip_bytes({"demo/algorithm.yml": ALGO_YML, "demo/run.sh": RUN_SH})}


def test_a_record_is_fetched_extracted_and_cached(serve):
    serve(_payload())
    dest = registry._fetch_record(RECID, None, lambda *_: None)
    assert (dest / "algorithm.yml").read_bytes() == ALGO_YML
    assert (dest / "run.sh").read_bytes() == RUN_SH
    assert dest.name == RECID


def test_a_second_fetch_is_a_cache_hit(serve, monkeypatch):
    serve(_payload())
    dest = registry._fetch_record(RECID, None, lambda *_: None)
    monkeypatch.setattr(registry, "_http_bytes",
                        lambda url: pytest.fail("a cached record must not hit the network"))
    assert registry._fetch_record(RECID, None, lambda *_: None) == dest


def test_a_registry_checksum_mismatch_is_refused(serve):
    """The pinned sha256 is what makes a version DOI reproduce byte-for-byte."""
    serve(_payload(), corrupt=_zip_bytes({"demo/algorithm.yml": b"slug: tampered\n"}))
    with pytest.raises(RuntimeError, match="pinned in the registry"):
        registry._fetch_record(RECID, "sha256:" + "0" * 64, lambda *_: None)


def test_a_zenodo_checksum_mismatch_is_refused_even_without_a_pin(serve):
    """Non-zip files were never checked at all; now every listed file is."""
    files = {"algorithm.yml": ALGO_YML, "method.zip": _zip_bytes({"demo/algorithm.yml": ALGO_YML})}
    serve(files, corrupt=b"not a zip at all")
    with pytest.raises(RuntimeError, match="checksum mismatch"):
        registry._fetch_record(RECID, None, lambda *_: None)


def test_a_file_zenodo_states_no_checksum_for_is_refused(serve):
    serve(_payload(), drop_checksum=("method.zip",))
    with pytest.raises(RuntimeError, match="states no checksum"):
        registry._fetch_record(RECID, None, lambda *_: None)


def test_a_record_without_an_algorithm_yml_is_refused(serve):
    serve({"method.zip": _zip_bytes({"demo/readme.md": b"nothing here\n"})})
    with pytest.raises(RuntimeError, match="no algorithm.yml"):
        registry._fetch_record(RECID, None, lambda *_: None)


@pytest.mark.parametrize("scenario", ["checksum", "no-manifest"])
def test_a_failed_fetch_leaves_no_cache_entry_behind(serve, tmp_path, scenario):
    """The point of the atomic rename: a failure must not leave anything that reads as 'cached',
    and must not leave a staging directory lying around either."""
    if scenario == "checksum":
        serve(_payload(), corrupt=b"garbage")
        pinned = "sha256:" + "0" * 64
    else:
        serve({"method.zip": _zip_bytes({"demo/readme.md": b"x\n"})})
        pinned = None
    with pytest.raises(RuntimeError):
        registry._fetch_record(RECID, pinned, lambda *_: None)
    cache = tmp_path / "cache" / "methods"
    assert not (cache / RECID).exists()
    left = list(cache.iterdir()) if cache.exists() else []
    assert left == [], f"a staging directory was left in the cache: {left}"


def test_a_stale_partial_cache_entry_is_replaced_wholesale(serve, tmp_path):
    """A pre-existing directory for this record is swapped out, not merged into."""
    stale = tmp_path / "cache" / "methods" / RECID
    stale.mkdir(parents=True)
    (stale / "leftover.txt").write_text("from an older version\n")
    serve(_payload())
    dest = registry._fetch_record(RECID, None, lambda *_: None)
    assert (dest / "algorithm.yml").exists()
    assert not (dest / "leftover.txt").exists()
