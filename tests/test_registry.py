"""Unit tests for the Zenodo method registry resolver (network-free parts)."""

from __future__ import annotations

import pytest

from qsm_ci import registry

FAKE = {
    "tkd": {
        "concept_doi": "10.5281/zenodo.111",
        "concept_recid": "111",
        "latest": "1.2",
        "versions": {
            "1.1": {"version_doi": "10.5281/zenodo.112", "record_id": "112", "checksum": "sha256:aa"},
            "1.2": {"version_doi": "10.5281/zenodo.113", "record_id": "113", "checksum": "sha256:bb"},
        },
    },
}


@pytest.fixture(autouse=True)
def _inject_mapping(monkeypatch):
    monkeypatch.setattr(registry, "_mapping_cache", FAKE)


@pytest.mark.parametrize("target,expected", [
    ("tkd", ("slug", "tkd")),
    ("tkd@1.1", ("version", ("tkd", "1.1"))),
    ("doi:10.5281/zenodo.113", ("recid", "113")),
    ("10.5281/zenodo.113", ("recid", "113")),
    ("https://doi.org/10.5281/zenodo.999", ("recid", "999")),
    ("https://zenodo.org/records/777", ("recid", "777")),
    ("./algorithms/tkd", ("slug", "./algorithms/tkd")),  # a path stays a path (local wins upstream)
])
def test_parse_target(target, expected):
    assert registry.parse_target(target) == expected


def test_record_id_resolution():
    assert registry._record_id("slug", "tkd", FAKE) == "113"          # latest
    assert registry._record_id("version", ("tkd", "1.1"), FAKE) == "112"
    assert registry._record_id("recid", "555", FAKE) == "555"
    assert registry._record_id("slug", "nope", FAKE) is None
    assert registry._record_id("version", ("tkd", "9.9"), FAKE) is None


def test_expected_checksum():
    assert registry._expected_checksum("slug", "tkd", FAKE) == "sha256:bb"
    assert registry._expected_checksum("version", ("tkd", "1.1"), FAKE) == "sha256:aa"
    assert registry._expected_checksum("recid", "113", FAKE) is None   # raw DOI → no known checksum


def test_describe_for_citation():
    d = registry.describe("tkd")
    assert d["version"] == "1.2" and d["concept_doi"] == "10.5281/zenodo.111"
    assert d["version_doi"] == "10.5281/zenodo.113"
    assert registry.describe("tkd@1.1")["version_doi"] == "10.5281/zenodo.112"
    assert registry.describe("unknown-method") is None


def test_resolve_unknown_returns_none():
    # a slug not in the registry (and no network hit) resolves to None
    assert registry.resolve("definitely-not-a-method") is None
