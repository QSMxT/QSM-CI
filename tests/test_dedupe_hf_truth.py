"""Guards on which per-run ground-truth copies dedupe_hf_truth.py may delete.

The original version deleted every `*__truth*.nii.gz` in the repo that the ONE index it was handed
did not reference. That is only sound if that index is the complete picture, and it never is: in
2026-09 the deployed results/index.json held 1,162 runs while the HPC's held 17,195, with 234 runs
present in the deployed one and absent from the other. Running it on the HPC — which is exactly what
was about to happen — would have deleted 165 truth volumes the live site was serving.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import dedupe_hf_truth as dd  # noqa: E402

A = "runA__truth.nii.gz"
SHARED_URL = "https://huggingface.co/datasets/qsmxt/qsm-ci-volumes/resolve/main/truth/p/chimap.nii.gz"


def _split(legacy, repointed=(), elsewhere=(), shared_sha=("sha-a",), sha_of=None):
    sha_of = sha_of if sha_of is not None else {p: "sha-a" for p in legacy}
    return dd.deletable(list(legacy), set(repointed), set(elsewhere), set(shared_sha), sha_of)


def test_deletes_only_a_file_whose_reference_it_just_repointed():
    delete, keep = _split([A], repointed=[A])
    assert delete == [A] and keep == []


def test_a_file_no_supplied_index_references_is_kept_not_deleted():
    """The bug: absence from the index you happen to hold is not evidence nothing uses it."""
    delete, keep = _split([A], repointed=[])
    assert delete == []
    assert keep[0][1].startswith("not repointed")


def test_a_file_another_index_references_is_kept():
    delete, keep = _split([A], repointed=[A], elsewhere=[A])
    assert delete == []
    assert keep[0][1] == "referenced by another index"


def test_content_must_be_preserved_under_truth_before_deleting():
    delete, keep = _split([A], repointed=[A], shared_sha=["sha-other"])
    assert delete == []
    assert keep[0][1] == "no shared truth/ file has this content"


def test_a_file_with_no_sha_is_kept():
    delete, keep = _split([A], repointed=[A], sha_of={})
    assert delete == []
    assert "cannot prove" in keep[0][1]


def test_the_2026_09_near_miss_is_now_refused():
    """165 files the deployed index referenced, absent from the index being processed."""
    site_only = [f"chisep-run{i}__truth.nii.gz" for i in range(165)]
    processed = [f"other-run{i}__truth.nii.gz" for i in range(50)]
    legacy = site_only + processed
    sha_of = {p: "sha-a" for p in legacy}
    # Processing only the HPC index: the site's 165 are not repointed here, so they survive
    # WITHOUT anyone having to remember to pass the other index.
    delete, keep = dd.deletable(legacy, set(processed), set(), {"sha-a"}, sha_of)
    assert set(delete) == set(processed)
    assert {p for p, _ in keep} == set(site_only)


def test_passing_more_indexes_can_only_protect_more():
    legacy = [A, "runB__truth.nii.gz"]
    sha_of = {p: "sha-a" for p in legacy}
    few, _ = dd.deletable(legacy, set(legacy), set(), {"sha-a"}, sha_of)
    many, _ = dd.deletable(legacy, set(legacy), {A}, {"sha-a"}, sha_of)
    assert set(many) < set(few)


def test_legacy_pattern_matches_both_truth_kinds_and_nothing_else():
    assert dd.LEGACY.search("a__truth.nii.gz")
    assert dd.LEGACY.search("a__truth-dia.nii.gz")
    assert not dd.LEGACY.search("truth/phantom/chimap.nii.gz")
    assert not dd.LEGACY.search("a__recon.nii.gz")


def test_a_file_both_indexes_reference_is_protected_by_the_other_one():
    """The overlap case: rewriting index 1 does not license deleting what index 2 also points at.

    Tempting to compute "referenced elsewhere" as (union of all indexes) - (what we rewrote), which
    silently strips protection from exactly the files BOTH indexes share — the common case, since
    two indexes of the same repo overlap heavily.
    """
    shared_by_both = A
    delete, keep = _split([shared_by_both], repointed=[shared_by_both], elsewhere=[shared_by_both])
    assert delete == []
    assert keep[0][1] == "referenced by another index"


# ---- the repoint record that hands phase 1 off to phase 2 --------------------------------------
# Without it the delete pass is a no-op forever: it re-reads an index that has ALREADY been
# rewritten, finds no legacy references, and so has nothing it is allowed to delete.

def test_delete_pass_cannot_rederive_repointed_from_a_rewritten_index(tmp_path):
    idx = tmp_path / "index.json"
    idx.write_text(json.dumps({"runs": [{"id": "r", "volumes": {"truth": SHARED_URL}}]}))
    # the rewritten index mentions no legacy path at all
    assert dd.load_pending([idx]) == set()


def test_pending_record_round_trips(tmp_path):
    idx = tmp_path / "index.json"
    dd.pending_path(idx).write_text(json.dumps({"paths": ["runA__truth.nii.gz"]}))
    assert dd.load_pending([idx]) == {"runA__truth.nii.gz"}


def test_pending_records_union_across_indexes(tmp_path):
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    dd.pending_path(a).write_text(json.dumps({"paths": ["runA__truth.nii.gz"]}))
    dd.pending_path(b).write_text(json.dumps({"paths": ["runB__truth.nii.gz"]}))
    assert dd.load_pending([a, b]) == {"runA__truth.nii.gz", "runB__truth.nii.gz"}


def test_a_recorded_path_still_needs_the_other_guards(tmp_path):
    """The record says a repoint happened; it does not override 'someone else references it'."""
    delete, keep = _split([A], repointed=[A], elsewhere=[A])
    assert delete == [] and keep[0][1] == "referenced by another index"


# ---- copies whose run ALREADY points at a shared file -------------------------------------------
# A run migrated by an earlier publish leaves its per-run copy behind with nothing referencing it and
# no repoint record, so it is invisible to deletable() (never repointed) AND to publish_volumes'
# --prune-flat (the run is live, so not retired). 75 of these survived the 2026-09 collapse.

REPO = "qsmxt/qsm-ci-volumes"
BASE = f"https://huggingface.co/datasets/{REPO}/resolve/main/"
SHARED_P = "truth/p/chimap.nii.gz"


def _rows(truth_url):
    return [{"id": "runA", "volumes": {"truth": truth_url}}]


def test_detected_when_the_run_points_at_identical_shared_bytes():
    got = dd.already_shared([A], _rows(BASE + SHARED_P), REPO, {A: "s1", SHARED_P: "s1"})
    assert got == {A}


def test_not_detected_when_the_shared_bytes_differ():
    """Different content means the run was scored against something else — never delete it."""
    got = dd.already_shared([A], _rows(BASE + SHARED_P), REPO, {A: "s1", SHARED_P: "s2"})
    assert got == set()


def test_not_detected_when_the_run_still_points_at_the_legacy_file():
    got = dd.already_shared([A], _rows(BASE + A), REPO, {A: "s1", SHARED_P: "s1"})
    assert got == set()


def test_not_detected_when_the_run_is_gone():
    """A retired run is --prune-flat's business, and rests on different evidence."""
    assert dd.already_shared([A], [], REPO, {A: "s1", SHARED_P: "s1"}) == set()


def test_not_detected_without_a_sha_for_either_side():
    assert dd.already_shared([A], _rows(BASE + SHARED_P), REPO, {A: "s1"}) == set()
    assert dd.already_shared([A], _rows(BASE + SHARED_P), REPO, {SHARED_P: "s1"}) == set()
