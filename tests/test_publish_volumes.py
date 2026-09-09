"""What publish_volumes.py puts on — and takes off — the Hugging Face volumes repo.

Two concerns, both about not letting the Hub drift out of step with the results:
ground truth is uploaded once per (phantom, artifact) rather than once per run, and `--prune`
removes volumes that are no longer produced.

## Shared ground truth

Ground truth reaches the Hugging Face volumes repo ONCE per (phantom, artifact), never once per run.

publish_volumes.py used to upload `<run-id>__truth.nii.gz` for every scored run — hundreds of
byte-identical copies of each phantom's χ map. These pin the sharing rules: the Hub path is derived
from the phantom and the artifact the run's last stage produces, identical bytes collapse to one
upload, different bytes for the same name never overwrite each other, and both the new `truth.ref`
pointer pipeline.py writes and a legacy per-run `truth.nii.gz` resolve to the shared name.
"""
import importlib.util
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("publish_volumes", ROOT / "scripts" / "publish_volumes.py")
pv = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pv)


def test_truth_name_is_phantom_and_produced_artifact():
    assert pv.truth_name({"stage": "dipole", "phantom": "sim"}, "truth") == "truth/sim/chimap.nii.gz"
    assert pv.truth_name({"stage": "bfr", "phantom": "sim"}, "truth") == "truth/sim/localfield.nii.gz"
    assert pv.truth_name({"stage": "field-mapping", "phantom": "sim"}, "truth") == "truth/sim/totalfield.nii.gz"
    # a composed span ends in the dipole stage -> its truth is the chimap
    assert pv.truth_name({"stage": "field-mapping+bfr+dipole", "phantom": "sim"}, "truth") == "truth/sim/chimap.nii.gz"
    # χ-separation: the plain set is χ+, the -dia set is χ−
    assert pv.truth_name({"stage": "chi-separation", "phantom": "chisep-mc"}, "truth") == "truth/chisep-mc/chi-para.nii.gz"
    assert pv.truth_name({"stage": "chi-separation", "phantom": "chisep-mc"}, "truth-dia") == "truth/chisep-mc/chi-dia.nii.gz"


def test_truth_name_defaults_for_historical_sim_rows():
    # The QSM sim track's early rows carry no `phantom`; they belong to the default `sim` phantom.
    assert pv.truth_name({"stage": "dipole", "track": "sim"}, "truth") == "truth/sim/chimap.nii.gz"
    assert pv.truth_name({"stage": "dipole", "track": "invivo"}, "truth") == "truth/invivo/chimap.nii.gz"
    # An unrecognisable stage still yields a stable, phantom-scoped name rather than crashing.
    assert pv.truth_name({"stage": "mystery", "phantom": "sim"}, "truth") == "truth/sim/truth.nii.gz"


def test_assign_truth_names_shares_identical_content_and_never_overwrites():
    by_sha, refs = pv.assign_truth_names([
        ("a", "sha-one", "truth/sim/chimap.nii.gz"),
        ("b", "sha-one", "truth/sim/chimap.nii.gz"),          # same bytes -> same file
        ("c", "sha-two", "truth/sim/chimap.nii.gz"),          # same name, different bytes -> suffixed
        ("d", "sha-three", "truth/sim/localfield.nii.gz"),
    ])
    assert refs["a"] == refs["b"] == "truth/sim/chimap.nii.gz"
    assert refs["c"] == "truth/sim/chimap-sha-two.nii.gz"   # `-<sha[:8]>` suffix
    assert refs["d"] == "truth/sim/localfield.nii.gz"
    assert len(by_sha) == 3 and len(set(by_sha.values())) == 3


def _nii(path: Path, seed: int):
    import nibabel as nib
    import numpy as np
    rng = np.random.default_rng(seed)
    nib.save(nib.Nifti1Image(rng.normal(size=(4, 4, 4)).astype("float32"), np.eye(4)), str(path))


def test_resolve_truth_pointer_and_legacy_collapse_to_one_upload(tmp_path):
    results = tmp_path / "results"
    shared = results / pv.TRUTH_DIR / "sim" / "chimap.nii.gz"
    shared.parent.mkdir(parents=True)
    _nii(shared, seed=1)
    # run A: the pointer pipeline.py now writes; run B: a legacy per-run copy of the SAME truth;
    # run C: a legacy copy of a DIFFERENT truth (another phantom).
    for rid in ("a-iso", "b-iso", "c-iso"):
        (results / rid).mkdir()
    (results / "a-iso" / "truth.ref").write_text(f"{pv.TRUTH_DIR}/sim/chimap.nii.gz\n")
    (results / "b-iso" / "truth.nii.gz").write_bytes(shared.read_bytes())
    _nii(results / "c-iso" / "truth.nii.gz", seed=2)
    rows = {"a-iso": {"stage": "dipole", "phantom": "sim"},
            "b-iso": {"stage": "dipole", "phantom": "sim"},
            "c-iso": {"stage": "dipole", "phantom": "invivo", "track": "invivo"}}

    found = []
    for rid, row in rows.items():
        path, wanted = pv.resolve_truth(results / rid, results, row, "truth")
        found.append((rid, "truth", path, wanted))
    assert found[0][3] == "truth/sim/chimap.nii.gz"     # from the pointer
    assert found[1][3] == "truth/sim/chimap.nii.gz"     # derived from the row

    uploads, refs = pv.plan_truths(found)
    assert set(uploads) == {"truth/sim/chimap.nii.gz", "truth/invivo/chimap.nii.gz"}
    assert refs[("a-iso", "truth")] == refs[("b-iso", "truth")] == "truth/sim/chimap.nii.gz"
    assert refs[("c-iso", "truth")] == "truth/invivo/chimap.nii.gz"
    # a run with no truth at all (DNF / no-ground-truth track) resolves to None
    (results / "d-iso").mkdir()
    assert pv.resolve_truth(results / "d-iso", results, {"stage": "dipole"}, "truth") is None


def test_emit_volumes_writes_one_shared_truth_and_a_pointer(tmp_path, monkeypatch):
    """pipeline.emit_volumes stages the truth ONCE per phantom and leaves a pointer per run — the
    contract publish_volumes.resolve_truth relies on."""
    _spec = importlib.util.spec_from_file_location("pipeline", ROOT / "scripts" / "pipeline.py")
    pipeline = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(pipeline)
    monkeypatch.setattr(pipeline, "ROOT", tmp_path)
    gt = tmp_path / "data" / "sim" / "groundtruth"
    gt.mkdir(parents=True)
    _nii(gt / "chimap.nii.gz", seed=3)
    recon = tmp_path / "recon.nii.gz"
    _nii(recon, seed=4)
    mask = tmp_path / "mask.nii.gz"
    _nii(mask, seed=5)

    for rid in ("x-iso", "y-iso"):
        pipeline.emit_volumes(rid, recon, gt / "chimap.nii.gz", mask)

    results = tmp_path / "results"
    shared = results / pipeline.TRUTH_DIR / "sim" / "chimap.nii.gz"
    assert shared.read_bytes() == (gt / "chimap.nii.gz").read_bytes()
    assert not (results / "x-iso" / "truth.nii.gz").exists()          # no per-run copy any more
    for rid in ("x-iso", "y-iso"):
        assert (results / rid / "truth.ref").read_text().strip() == f"{pipeline.TRUTH_DIR}/sim/chimap.nii.gz"
        assert (results / rid / "recon.nii.gz").exists() and (results / rid / "error.nii.gz").exists()
        path, name = pv.resolve_truth(results / rid, results, {"stage": "dipole", "phantom": "sim"}, "truth")
        assert (path, name) == (shared, "truth/sim/chimap.nii.gz")


# --- --prune ---------------------------------------------------------------------------------
# Uploading is an upsert, so a run that stops being produced keeps its old volume and the viewer
# serves a stale recon forever. `--prune` removes those. Because it deletes published data, the
# safety scope is what these check: never the flat root, never the shared ground truth, never
# something the index still points at, and never a suspiciously large fraction of a directory.

REPO = "qsmxt/qsm-ci-volumes"
PREFIX = f"https://huggingface.co/datasets/{REPO}/resolve/main/"


# The real delete op needs huggingface_hub; the logic under test does not. Swap in a stand-in so
# these run anywhere rather than skipping (a skipped safety test protects nothing).
pv._delete_op = lambda path: SimpleNamespace(path_in_repo=path)


class FakeApi:
    """Records deletions instead of performing them."""

    def __init__(self, files):
        self.files = list(files)
        self.deleted = []

    def list_repo_files(self, repo, repo_type=None):
        return list(self.files)

    def create_commit(self, repo, repo_type=None, operations=(), commit_message=""):
        self.deleted += [op.path_in_repo for op in operations]


def _prune(files, uploaded, keep=(), scopes=("repro/acq1/",), dry_run=False, superseded=()):
    api = FakeApi(files)
    n = pv._prune(api, REPO, set(uploaded), set(keep), set(scopes), dry_run, set(superseded))
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


def test_shared_ground_truth_is_never_pruned():
    """truth/<phantom>/<artifact> is referenced by every run on that phantom, including runs
    outside this publish, and is deduplicated by content hash. A publish that happens to upload
    one must not make the whole truth/ tree a prune target — housekeeping there belongs to
    dedupe_hf_truth.py."""
    files = ["truth/sim/chimap.nii.gz", "truth/sim/localfield.nii.gz",
             "repro/acq1/a__recon.nii.gz", "repro/acq1/b__recon.nii.gz",
             "repro/acq1/gone__recon.nii.gz"]
    deleted, _ = _prune(files, uploaded=["repro/acq1/a__recon.nii.gz",
                                         "repro/acq1/b__recon.nii.gz",
                                         "truth/sim/chimap.nii.gz"],
                        scopes=("repro/acq1/", "truth/sim/"))
    assert deleted == ["repro/acq1/gone__recon.nii.gz"]
    assert not any(f.startswith("truth/") for f in deleted)


def test_index_referenced_volume_survives_even_if_not_re_uploaded():
    """A volume can be live in index.json but absent from this machine's results/ dir."""
    files = ["repro/acq1/a__recon.nii.gz", "repro/acq1/b__recon.nii.gz"]
    deleted, n = _prune(files, uploaded=["repro/acq1/a__recon.nii.gz"],
                        keep=["repro/acq1/b__recon.nii.gz"])
    assert deleted == [] and n == 0




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

    assert pv._prune(Broken([]), REPO, set(), set(), {"repro/acq1/"}, False) == 0


def test_indexed_paths_collects_every_url_kind():
    rows = [{"volumes": {"recon": PREFIX + "a__recon.nii.gz",
                         "truth": PREFIX + "a__truth.nii.gz"},
             "resources_url": PREFIX + "a__resources.json",
             "regions_url": PREFIX + "a__regions.json"},
            {"volumes": {"recon": "https://elsewhere.example/b.nii.gz"}},   # foreign host ignored
            {}]                                                            # no volumes at all
    assert pv._indexed_paths(rows, REPO) == {
        "a__recon.nii.gz", "a__truth.nii.gz", "a__resources.json", "a__regions.json"}


# ---- prune flag parsing ------------------------------------------------------------------------
# A dry run is the first thing anyone reaches for before deleting published data, so it must never
# be a silent no-op. It was exactly that on the HPC side, where an older copy of the script had no
# prune at all: unknown `--` flags are filtered out of the positional args, so the job published,
# pruned nothing, printed nothing about pruning, and exited 0.

def test_prune_dry_run_alone_enables_the_prune_path():
    assert pv._prune_flags(["publish_volumes.py", "results", "--prune-dry-run"]) == (True, True)



def test_plain_prune_deletes_for_real():
    assert pv._prune_flags(["publish_volumes.py", "--prune"]) == (True, False)


def test_no_prune_flag_means_no_prune():
    assert pv._prune_flags(["publish_volumes.py", "results"]) == (False, False)


def test_prune_substring_does_not_match_the_longer_flags():
    # "--prune" must be matched as a whole argument, never as a prefix of --prune-dry-run
    assert pv._prune_flags(["publish_volumes.py", "--prune-dry-run"]) == (True, True)


# ---- shared intermediates are addressed by CONVENTION, not by any index URL ---------------------
# The repo holds three kinds of file that belong to no single run: the acquisition's magnitude, the
# field-mapping method's total field, and the (field mapping, bg removal) pair's local field.
# Hundreds of pipelines share each, so nothing records them in index.json — the viewer rebuilds
# their URLs from the naming pattern. They are therefore invisible to both of prune's tests, and a
# keep-set built from runs alone called all 621 of them orphans on a live repo.

INTERMEDIATES = ["repro/acq1/acq1__magnitude.nii.gz",
                 "repro/acq1/laplacian-qsmci__totalfield.nii.gz",
                 "repro/acq1/laplacian-qsmci_vsharp-qsmrs__localfield.nii.gz"]


def test_shared_intermediates_are_never_pruned():
    deleted, n = _prune(INTERMEDIATES + ["repro/acq1/gone__recon.nii.gz"],
                        uploaded=[], keep=[])
    assert deleted == ["repro/acq1/gone__recon.nii.gz"]      # only the run artifact goes
    assert n == 1


def test_intermediates_survive_even_when_nothing_else_is_in_scope():
    deleted, n = _prune(INTERMEDIATES, uploaded=[], keep=[])
    assert deleted == [] and n == 0


def test_run_artifact_classifies_every_kind_this_script_uploads():
    for kind in ("recon", "error", "truth", "resources", "regions",
                 "recon-dia", "error-dia", "truth-dia"):
        ext = "json" if kind in ("resources", "regions") else "nii.gz"
        got = pv._run_artifact(f"repro/acq1/some~pipe-cmp-acq1__{kind}.{ext}", "repro/acq1/")
        assert got == ("some~pipe-cmp-acq1", kind), kind


def test_run_artifact_rejects_the_shared_intermediate_kinds():
    for f in INTERMEDIATES:
        assert pv._run_artifact(f, "repro/acq1/") is None, f


def test_unrecognised_artifact_kind_is_left_alone_not_deleted():
    # a future artifact this script does not yet know about must not be swept up as an orphan
    deleted, n = _prune(["repro/acq1/pipe-cmp-acq1__somethingnew.nii.gz"], uploaded=[], keep=[])
    assert deleted == [] and n == 0


# ---- flat-root orphans: retired runs, and files a publish supersedes itself --------------------
# The flat root is outside every sharded prune scope, so nothing could attribute a file there. Two
# ways it fills up, and they need different evidence: a run RENAMED or RETIRED leaves its volumes
# (absence-based, hence the coverage precondition), and the shared-truth migration leaves the old
# per-run copy (positively attributable — this publish wrote its replacement).

FLAT = ["runA__recon.nii.gz", "runA__truth.nii.gz", "gone__recon.nii.gz",
        "truth/p/chimap.nii.gz", "repro/acq1/x__recon.nii.gz"]


def test_flat_orphans_finds_only_retired_runs():
    orphans, coverage = pv.flat_orphans(FLAT, {"runA"}, set())
    assert orphans == ["gone__recon.nii.gz"]
    assert coverage == 2 / 3          # runA's two files of the three flat run artifacts


def test_flat_orphans_ignores_shared_truth_and_sharded_paths():
    orphans, _ = pv.flat_orphans(FLAT, set(), set())
    assert "truth/p/chimap.nii.gz" not in orphans
    assert "repro/acq1/x__recon.nii.gz" not in orphans


def test_flat_orphans_tolerates_sanitised_run_ids():
    # index ids use ~ / +, hub names sanitise both to _
    orphans, _ = pv.flat_orphans(["a_b_c-cmp__recon.nii.gz"], {"a~b~c-cmp"}, set())
    assert orphans == []


def test_flat_orphans_keeps_anything_an_index_still_points_at():
    orphans, _ = pv.flat_orphans(FLAT, set(), {"gone__recon.nii.gz"})
    assert "gone__recon.nii.gz" not in orphans


def test_flat_coverage_is_a_precondition_on_the_input_not_a_cap_on_the_output():
    # a correct large cleanup: indexes explain most of the root, few orphans -> high coverage
    files = [f"run{i}__recon.nii.gz" for i in range(90)] + [f"old{i}__recon.nii.gz" for i in range(10)]
    _, good = pv.flat_orphans(files, {f"run{i}" for i in range(90)}, set())
    # an incomplete index list: almost nothing is explained, though the deletion would be just as big
    _, bad = pv.flat_orphans(files, {"run0"}, set())
    assert good >= pv.FLAT_COVERAGE_MIN > bad


def test_superseded_paths_are_pruned_despite_being_outside_every_scope():
    deleted, n = _prune(["runA__truth.nii.gz", "repro/acq1/keep__recon.nii.gz"],
                        uploaded=["repro/acq1/keep__recon.nii.gz"],
                        superseded=["runA__truth.nii.gz"])
    assert deleted == ["runA__truth.nii.gz"] and n == 1


def test_a_superseded_path_the_index_still_references_is_not_pruned():
    deleted, n = _prune(["runA__truth.nii.gz"], uploaded=[], keep=["runA__truth.nii.gz"],
                        superseded=[])
    assert deleted == [] and n == 0
