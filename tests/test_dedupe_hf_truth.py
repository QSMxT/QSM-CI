"""Guards on which per-run ground-truth copies dedupe_hf_truth.py may delete.

The original version deleted every `*__truth*.nii.gz` in the repo that the ONE index it was handed
did not reference. That is only sound if that index is the complete picture, and it never is: in
2026-09 the deployed results/index.json held 1,162 runs while the HPC's held 17,195, with 234 runs
present in the deployed one and absent from the other. Running it on the HPC — which is exactly what
was about to happen — would have deleted 165 truth volumes the live site was serving.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import dedupe_hf_truth as dd  # noqa: E402

A = "runA__truth.nii.gz"


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
