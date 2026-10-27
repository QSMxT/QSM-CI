"""scripts/provenance.py: the scored date and method versions the submission page shows."""
import provenance


def test_backfill_fills_missing_fields_once_and_skips_local_rows(monkeypatch):
    calls = []
    monkeypatch.setattr(provenance, "run_started", lambda rid: calls.append(rid) or "2026-10-19T14:45:34Z")
    monkeypatch.setattr(provenance, "method_commit", lambda slug, sha: {"commit": f"{slug}@{sha}", "date": "2026-10-01T00:00:00Z"})
    doc = {"runs": [
        {"id": "a", "slug": "tkd", "ci_run": "5.1", "ci_sha": "s1"},
        {"id": "b", "combo": {"field_mapping": "gt", "bfr": "vsharp", "dipole": "tkd"}, "ci_run": "5.2", "ci_sha": "s1"},
        {"id": "c", "slug": "tkd", "ci_run": "6.1", "ci_sha": "s2", "scored_at": "kept", "method_versions": {"tkd": "kept"}},
        {"id": "d", "slug": "tkd"},                                   # local row: no CI run to date it by
    ]}
    assert provenance.backfill(doc) == (2, 2)
    a, b, c, d = doc["runs"]
    assert a["scored_at"] == b["scored_at"] == "2026-10-19T14:45:34Z"
    assert calls == ["5"]                                             # one lookup per run, not per row
    assert list(b["method_versions"]) == ["vsharp", "tkd"] and b["method_versions"]["tkd"]["commit"] == "tkd@s1"
    assert c["scored_at"] == "kept" and c["method_versions"] == {"tkd": "kept"}
    assert "scored_at" not in d and "method_versions" not in d
    assert provenance.backfill(doc) == (0, 0)                         # idempotent


def test_backfill_leaves_a_row_undated_when_the_run_lookup_fails(monkeypatch):
    monkeypatch.setattr(provenance, "run_started", lambda rid: None)
    monkeypatch.setattr(provenance, "method_commit", lambda slug, sha: None)
    doc = {"runs": [{"id": "a", "slug": "tkd", "ci_run": "5.1", "ci_sha": "s1"}]}
    assert provenance.backfill(doc) == (0, 0) and doc["runs"][0] == {"id": "a", "slug": "tkd", "ci_run": "5.1", "ci_sha": "s1"}
