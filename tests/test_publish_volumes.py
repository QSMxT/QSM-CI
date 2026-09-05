"""Unit tests for the volume-prune logic (scripts/publish_volumes.py).

Uploading to the Hub is an UPSERT, so a run that stops being produced keeps its old volume and the
viewer serves a stale recon forever. `--prune` deletes those. Because it deletes published data,
its safety scope is what actually matters here: never the flat root, never something the index
still points at, and never a suspiciously large fraction of a directory.
"""
import importlib.util
from pathlib import Path

import pytest

# publish_volumes imports huggingface_hub at module scope. It's an optional dependency (only the
# publishing path needs it), so skip cleanly rather than reporting a failure on a machine that
# simply doesn't have it installed.
pytest.importorskip("huggingface_hub",
                    reason="huggingface_hub not installed — publish_volumes can't be imported")

_spec = importlib.util.spec_from_file_location(
    "publish_volumes", Path(__file__).resolve().parent.parent / "scripts" / "publish_volumes.py")
pv = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pv)

REPO = "qsmxt/qsm-ci-volumes"
PREFIX = f"https://huggingface.co/datasets/{REPO}/resolve/main/"


class FakeApi:
    """Records deletions instead of performing them."""

    def __init__(self, files):
        self.files = list(files)
        self.deleted = []

    def list_repo_files(self, repo, repo_type=None):
        return list(self.files)

    def create_commit(self, repo, repo_type=None, operations=(), commit_message=""):
        self.deleted += [op.path_in_repo for op in operations]


def _prune(files, uploaded, keep=(), scopes=("repro/acq1/",), dry_run=False, force=False):
    api = FakeApi(files)
    n = pv._prune(api, REPO, set(uploaded), set(keep), set(scopes), dry_run, force)
    return api.deleted, n


def test_orphan_in_scope_is_deleted():
    files = ["repro/acq1/keep__recon.nii.gz", "repro/acq1/also__recon.nii.gz",
             "repro/acq1/gone__recon.nii.gz"]
    deleted, n = _prune(files, uploaded=["repro/acq1/keep__recon.nii.gz",
                                         "repro/acq1/also__recon.nii.gz"])
    assert deleted == ["repro/acq1/gone__recon.nii.gz"] and n == 1


def test_flat_root_is_never_pruned():
    """The root mixes tracks; a partial index must not be able to delete another track's volumes."""
    files = ["sim-run__recon.nii.gz", "invivo-run__recon.nii.gz"]
    deleted, n = _prune(files, uploaded=[], scopes=("",))
    assert deleted == [] and n == 0


def test_root_files_untouched_even_when_a_subdir_is_pruned():
    files = ["sim-run__recon.nii.gz", "invivo-run__recon.nii.gz",
             "repro/acq1/a__recon.nii.gz", "repro/acq1/b__recon.nii.gz",
             "repro/acq1/gone__recon.nii.gz"]
    deleted, _ = _prune(files, uploaded=["repro/acq1/a__recon.nii.gz",
                                         "repro/acq1/b__recon.nii.gz"],
                        scopes=("repro/acq1/", ""))
    assert deleted == ["repro/acq1/gone__recon.nii.gz"]


def test_other_acquisitions_are_out_of_scope():
    """A publish that touched acq1 must not delete acq2, whose runs it never saw."""
    files = ["repro/acq1/a__recon.nii.gz", "repro/acq1/b__recon.nii.gz",
             "repro/acq1/gone__recon.nii.gz", "repro/acq2/live__recon.nii.gz"]
    deleted, _ = _prune(files, uploaded=["repro/acq1/a__recon.nii.gz",
                                         "repro/acq1/b__recon.nii.gz"],
                        scopes=("repro/acq1/",))
    assert deleted == ["repro/acq1/gone__recon.nii.gz"]


def test_index_referenced_volume_survives_even_if_not_re_uploaded():
    """A volume can be live in index.json but absent from this machine's results/ dir."""
    files = ["repro/acq1/a__recon.nii.gz", "repro/acq1/b__recon.nii.gz"]
    deleted, n = _prune(files, uploaded=["repro/acq1/a__recon.nii.gz"],
                        keep=["repro/acq1/b__recon.nii.gz"])
    assert deleted == [] and n == 0


def test_large_deletion_is_refused_without_force():
    files = [f"repro/acq1/r{i}__recon.nii.gz" for i in range(10)]
    deleted, n = _prune(files, uploaded=["repro/acq1/r0__recon.nii.gz"])
    assert deleted == [] and n == 0            # 9/10 orphaned -> refused


def test_large_deletion_proceeds_with_force():
    files = [f"repro/acq1/r{i}__recon.nii.gz" for i in range(10)]
    deleted, n = _prune(files, uploaded=["repro/acq1/r0__recon.nii.gz"], force=True)
    assert n == 9 and "repro/acq1/r0__recon.nii.gz" not in deleted


def test_dry_run_deletes_nothing():
    files = ["repro/acq1/a__recon.nii.gz", "repro/acq1/b__recon.nii.gz",
             "repro/acq1/gone__recon.nii.gz"]
    deleted, n = _prune(files, uploaded=["repro/acq1/a__recon.nii.gz",
                                         "repro/acq1/b__recon.nii.gz"], dry_run=True)
    assert deleted == [] and n == 0


def test_list_failure_is_survivable():
    class Broken(FakeApi):
        def list_repo_files(self, repo, repo_type=None):
            raise RuntimeError("hub down")

    assert pv._prune(Broken([]), REPO, set(), set(), {"repro/acq1/"}, False, False) == 0


def test_indexed_paths_collects_every_url_kind():
    rows = [{"volumes": {"recon": PREFIX + "a__recon.nii.gz",
                         "truth": PREFIX + "a__truth.nii.gz"},
             "resources_url": PREFIX + "a__resources.json",
             "regions_url": PREFIX + "a__regions.json"},
            {"volumes": {"recon": "https://elsewhere.example/b.nii.gz"}},   # foreign host ignored
            {}]                                                            # no volumes at all
    assert pv._indexed_paths(rows, REPO) == {
        "a__recon.nii.gz", "a__truth.nii.gz", "a__resources.json", "a__regions.json"}
