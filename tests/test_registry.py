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


def test_list_falls_back_to_registry_without_checkout(monkeypatch):
    # A bare pip install (no ./algorithms) lists the published methods from the shipped registry.
    from qsm_ci import runner
    monkeypatch.setattr(registry, "_mapping_cache", {
        "tkd": {"latest": "2", "stage": "dipole", "name": "TKD",
                "versions": {"2": {"record_id": "2", "checksum": "sha256:aa"}}},
        "sharp": {"latest": "1", "stage": "bfr", "name": "SHARP",
                  "versions": {"1": {"record_id": "1", "checksum": "sha256:bb"}}},
    })
    monkeypatch.setattr(runner, "_algorithms_root", lambda: None)
    assert set(runner._list_algorithms()) == {("sharp", "bfr", "SHARP"), ("tkd", "dipole", "TKD")}
    help_text = runner._algorithms_help()
    assert "Published methods (fetched from Zenodo" in help_text
    assert "tkd" in help_text and "SHARP" in help_text


def test_unpublished_entry_resolves_to_none_not_keyerror(monkeypatch):
    """A method can be registered before its first Zenodo deposit (`versions: {}`, no `latest`) —
    publish-zenodo.py writes exactly that shape. Every lookup must treat it as "not published"."""
    monkeypatch.setattr(registry, "_mapping_cache", {**FAKE, "draft": {"name": "Draft", "stage": "bfr",
                                                                        "versions": {}}})
    assert registry._record_id("slug", "draft", registry.load_mapping()) is None
    assert registry._expected_checksum("slug", "draft", registry.load_mapping()) is None
    assert registry.describe("draft") is None
    assert not registry.is_published(registry.load_mapping()["draft"])
    assert registry.is_published(registry.load_mapping()["tkd"])
    msgs = []
    assert registry.resolve("draft", log=msgs.append) is None
    assert msgs and "no published version" in msgs[0]


def test_list_hides_unpublished_registry_entries(monkeypatch):
    from qsm_ci import runner
    monkeypatch.setattr(registry, "_mapping_cache", {**FAKE, "draft": {"name": "Draft", "stage": "bfr",
                                                                        "versions": {}}})
    monkeypatch.setattr(runner, "_algorithms_root", lambda: None)
    slugs = [s for s, _, _ in runner._list_algorithms()]
    assert "tkd" in slugs and "draft" not in slugs
