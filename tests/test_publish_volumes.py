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


def test_leading_slug_extracts_the_method_from_a_run_id():
    assert pv._leading_slug("nltv-iso-tuned") == "nltv"
    assert pv._leading_slug("gt~sharp~tkd-cmp") == "gt~sharp~tkd"
    assert pv._leading_slug("plain") == "plain"


def test_live_algo_slugs_reads_the_manifest():
    slugs = pv.live_algo_slugs()
    assert "rts-qsmrs" in slugs          # a current slug
    assert "rts" not in slugs            # its pre-rename name, which the orphans still carry


# ---- a partial publish must not look like a clean one ------------------------------------------
# Committing index.json without the failed runs' URLs is deliberate: losing a whole rescore because
# the Hub blinked would be worse. The defect was that it was SILENT — rc=0 under
# `continue-on-error: true` is a green job, and nothing retries short of another full rescore.

def test_exit_code_distinguishes_partial_from_clean_and_from_hard_error():
    # 0 clean, 2 index written but volumes partial, 1 reserved for a hard error
    import inspect
    src = inspect.getsource(pv.main)
    assert "return 2" in src, "a partial publish must not return 0"
    assert src.count("return 1") >= 1, "hard errors still return 1"


def test_annotate_emits_a_github_error_when_running_in_actions(monkeypatch, capsys, tmp_path):
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    pv._annotate("17 run(s) have no volume URLs")
    out = capsys.readouterr()
    assert "::error title=Incomplete volume publish::" in out.out
    assert "17 run(s) have no volume URLs" in summary.read_text()


def test_annotate_is_quiet_outside_actions(monkeypatch, capsys):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    pv._annotate("something")
    out = capsys.readouterr()
    assert "::error" not in out.out
    assert "something" in out.err          # still reported, just not as an annotation


# ---- layout: no directory may approach the Hub's per-directory cap -----------------------------
# The Hub rejects a whole commit once any directory holds more than HF_DIR_CAP files. In September
# 2026 the flat root hit it twice: a 79-run rescore published nothing, and a full rescore lost a
# 1,000-file batch — ~250 in-silico runs' viewers — while the job stayed green.

import hashlib  # noqa: E402
import json  # noqa: E402
import re  # noqa: E402
import sys  # noqa: E402
from collections import Counter  # noqa: E402


def test_repro_runs_keep_the_acquisition_directory_the_viewer_builds_urls_from():
    assert pv._subdir({"id": "a+b-cmp-acq1", "track": "repro", "phantom": "acq1"}) == "repro/acq1/"


def test_every_other_run_is_bucketed_under_its_phantom():
    sub = pv._subdir({"id": "medi-qsmrs-iso", "phantom": "sim"})
    assert re.fullmatch(r"runs/sim/[0-9a-f]{2}/", sub)
    assert sub == f"runs/sim/{hashlib.sha1(b'medi-qsmrs-iso').hexdigest()[:2]}/"   # from the id alone
    assert pv._subdir({"id": "x-iso-invivo", "phantom": "invivo", "track": "invivo"}).startswith("runs/invivo/")
    assert pv._subdir({"id": "old-iso", "track": "sim"}).startswith("runs/sim/")   # historical: no phantom


def _index_rows():
    return json.loads((ROOT / "results" / "index.json").read_text())["runs"]


def test_nothing_in_the_current_index_would_publish_to_the_flat_root():
    for row in _index_rows():
        if row.get("track") != "repro":
            assert "/" in pv._name(row["id"], "recon", "nii.gz", pv._subdir(row)), row["id"]


def test_the_current_index_leaves_every_directory_far_below_the_cap():
    per_dir = Counter()
    for row in _index_rows():
        kinds = pv.RUN_KINDS + (pv.DIA_KINDS if pv._is_chisep(row) else ())
        per_dir[pv._subdir(row)] += len(kinds)          # the most files a run can put there
    assert max(per_dir.values()) <= pv.HF_DIR_CAP // 20, per_dir.most_common(3)


# ---- a failed upload must not take a working viewer down with it --------------------------------

def test_a_failed_upload_falls_back_to_the_copy_already_at_that_path():
    name = "runs/sim/ab/runA__recon.nii.gz"
    got = pv.fallback_urls([("runA", "recon", name)], {name}, REPO)
    assert got == {"runA": {"recon": PREFIX + name}}


def test_a_failed_bucket_upload_falls_back_to_the_pre_sharding_flat_copy():
    got = pv.fallback_urls([("runA", "recon", "runs/sim/ab/runA__recon.nii.gz")],
                           {"runA__recon.nii.gz"}, REPO)
    assert got == {"runA": {"recon": PREFIX + "runA__recon.nii.gz"}}


def test_no_earlier_copy_means_no_url_rather_than_one_that_404s():
    assert pv.fallback_urls([("runA", "recon", "runs/sim/ab/runA__recon.nii.gz")], set(), REPO) == {}


def test_repro_paths_have_no_flat_copy_to_fall_back_to():
    # repro never lived in the root, so its root namesake (if any) is a different run's file
    assert pv._earlier_copies("repro/acq1/x__recon.nii.gz") == ("repro/acq1/x__recon.nii.gz",)


def test_relink_fills_only_what_a_scored_row_is_missing():
    rows = [
        {"id": "lost", "status": "ok", "phantom": "sim",
         "volumes": {"truth": PREFIX + "truth/scoring/chimap.nii.gz"}},
        {"id": "fine", "status": "ok", "phantom": "sim", "volumes": {"recon": PREFIX + "keep.nii.gz"}},
        {"id": "dnf", "status": "DNF", "phantom": "sim"},
    ]
    hub = {f"{rid}__{k}" for rid in ("lost", "fine", "dnf")
           for k in ("recon.nii.gz", "error.nii.gz", "resources.json", "regions.json")}
    got = pv.relink_urls(rows, hub, REPO)
    assert got["lost"] == {"recon": PREFIX + "lost__recon.nii.gz", "error": PREFIX + "lost__error.nii.gz",
                           "resources": PREFIX + "lost__resources.json",
                           "regions": PREFIX + "lost__regions.json"}
    assert "recon" not in got["fine"]                   # an existing URL is never second-guessed
    assert "dnf" not in got                             # a failed run must not show an old success


def test_relink_offers_the_chi_minus_maps_only_to_chi_separation_rows():
    hub = {"s__recon-dia.nii.gz", "q__recon-dia.nii.gz", "r__recon-dia.nii.gz"}
    rows = [{"id": "s", "status": "ok", "domain": "chisep", "stage": "r2prime-generation+chi-separation"},
            {"id": "q", "status": "ok", "stage": "dipole"},
            {"id": "r", "status": "ok", "domain": "chisep", "stage": "r2prime-generation"}]
    got = pv.relink_urls(rows, hub, REPO)
    assert got == {"s": {"recon-dia": PREFIX + "s__recon-dia.nii.gz"}}


def test_apply_urls_puts_sidecars_top_level_and_merges_or_replaces_volumes():
    row = {"volumes": {"truth": "T"}}
    pv._apply_urls(row, {"recon": "R", "resources": "S", "regions": "G"}, replace=False)
    assert row == {"volumes": {"truth": "T", "recon": "R"}, "resources_url": "S", "regions_url": "G"}
    pv._apply_urls(row, {"recon": "R2"}, replace=True)
    assert row["volumes"] == {"recon": "R2"}


def test_a_superseded_path_already_gone_from_the_hub_is_not_deleted_again():
    deleted, n = _prune(["repro/acq1/keep__recon.nii.gz"], uploaded=["repro/acq1/keep__recon.nii.gz"],
                        superseded=["never-published__recon.nii.gz"])
    assert deleted == [] and n == 0


class FakeHub:
    """Just enough of huggingface_hub for main(): commits land unless a path matches `reject`."""

    def __init__(self, files=(), reject=""):
        self.files, self.reject = set(files), reject

    def create_repo(self, *a, **k):
        pass

    def list_repo_files(self, repo, repo_type=None):
        return sorted(self.files)

    def create_commit(self, repo, repo_type=None, operations=(), commit_message=""):
        paths = [op.path_in_repo for op in operations]
        if self.reject and any(self.reject in p for p in paths):
            raise RuntimeError("Each directory in your git repo can only contain up to 10000 files.")
        for op in operations:   # an add carries the file to upload; the module's stand-in delete op doesn't
            (self.files.add if hasattr(op, "path_or_fileobj") else self.files.discard)(op.path_in_repo)


def _publish(tmp_path, monkeypatch, hub, *argv, runs=("runA", "runB"), extra_rows=()):
    """Run main() over scored sim runs (default runA and runB) against `hub`, one file per batch.
    `extra_rows` are index rows with no results dir — runs this publish did not produce.

    Two artifacts per run (a volume and a sidecar): with one file per batch, three rejected files
    in a row would trip main()'s circuit breaker before the other run uploads, and which run goes
    first depends on the hash buckets."""
    results = tmp_path / "results"
    rows = [{"id": rid, "status": "ok", "phantom": "sim", "stage": "dipole"} for rid in runs] + list(extra_rows)
    (results).mkdir()
    (results / "index.json").write_text(json.dumps({"runs": rows}))
    for rid in runs:
        (results / rid).mkdir()
        for f in ("recon.nii.gz", "resources.json"):
            (results / rid / f).write_text(rid)
    fake = SimpleNamespace(HfApi=lambda token=None: hub,
                           CommitOperationAdd=lambda path_in_repo, path_or_fileobj:
                           SimpleNamespace(path_in_repo=path_in_repo, path_or_fileobj=path_or_fileobj))
    monkeypatch.setitem(sys.modules, "huggingface_hub", fake)
    monkeypatch.setattr(pv, "BATCH", 1)
    monkeypatch.setattr(pv.time, "sleep", lambda s: None)
    monkeypatch.setenv("HF_VOLUMES_REPO", REPO)
    monkeypatch.setenv("HF_TOKEN", "t")
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.setattr(sys, "argv", ["publish_volumes.py", str(results), *argv])
    rc = pv.main()
    by_id = {r["id"]: r for r in json.loads((results / "index.json").read_text())["runs"]}
    report = results / "publish-incomplete.json"
    return rc, by_id, (json.loads(report.read_text()) if report.exists() else None)


def test_a_clean_publish_puts_every_run_in_its_bucket(tmp_path, monkeypatch):
    rc, by_id, report = _publish(tmp_path, monkeypatch, FakeHub())
    assert rc == 0 and report is None
    for rid, row in by_id.items():
        sub = pv._subdir(row)
        assert row["volumes"]["recon"] == PREFIX + f"{sub}{rid}__recon.nii.gz"
        assert row["resources_url"] == PREFIX + f"{sub}{rid}__resources.json"
        assert "volumes_stale" not in row


def test_the_september_failure_no_longer_blanks_runs_whose_files_are_on_the_hub(tmp_path, monkeypatch):
    """runB's uploads are rejected (the flat-root cap, replayed); its pre-sharding copies are there."""
    hub = FakeHub({"runB__recon.nii.gz", "runB__resources.json"}, reject="runB")
    rc, by_id, report = _publish(tmp_path, monkeypatch, hub)
    assert rc == 2                                                     # partial, not clean
    a, b = by_id["runA"], by_id["runB"]
    assert a["volumes"]["recon"].startswith(PREFIX + pv.RUNS_PREFIX) and "volumes_stale" not in a
    assert b["volumes"] == {"recon": PREFIX + "runB__recon.nii.gz"}
    assert b["resources_url"] == PREFIX + "runB__resources.json"
    assert b["volumes_stale"] is True
    assert report == {"failed_files": 2, "runs": [], "stale_runs": ["runB"]}


def test_a_failed_run_with_no_earlier_copy_is_reported_not_linked(tmp_path, monkeypatch):
    rc, by_id, report = _publish(tmp_path, monkeypatch, FakeHub(reject="runB"))
    assert rc == 2
    assert "volumes" not in by_id["runB"] and "volumes_stale" not in by_id["runB"]
    assert report["runs"] == ["runB"] and report["stale_runs"] == []


def test_a_clean_republish_clears_the_stale_flag(tmp_path, monkeypatch):
    results = tmp_path / "results"
    rc, _, _ = _publish(tmp_path, monkeypatch, FakeHub({"runB__recon.nii.gz"}, reject="runB"))
    assert rc == 2
    doc = json.loads((results / "index.json").read_text())
    assert any(r.get("volumes_stale") for r in doc["runs"])
    sys.modules["huggingface_hub"].HfApi().reject = ""                # the Hub is healthy again
    rc = pv.main()                                                     # same results dir
    rows = json.loads((results / "index.json").read_text())["runs"]
    assert rc == 0 and not any(r.get("volumes_stale") for r in rows)


# ---- pruning: replaced copies go, the only copy a row points at never does -------------------------
# The user-facing contract for automated housekeeping: a run whose latest upload failed keeps its
# earlier copy (flagged volumes_stale) and that copy is untouchable; a copy this publish demonstrably
# replaced is deleted on any publish; a retired run's files go only after a clean publish.

def _bucket(rid):
    return pv._subdir({"id": rid, "phantom": "sim"})


def test_a_stale_fallback_copy_is_never_pruned_while_the_replaced_one_is(tmp_path, monkeypatch):
    """Both runs have pre-sharding flat copies. runA's bucket upload lands (flat copy REPLACED →
    deleted); runB's is rejected (flat copy is its only copy → kept, row flagged stale)."""
    flat = {"runA__recon.nii.gz", "runA__resources.json", "runB__recon.nii.gz", "runB__resources.json"}
    hub = FakeHub(flat, reject="runB")
    rc, by_id, _ = _publish(tmp_path, monkeypatch, hub, "--prune")
    assert rc == 2
    assert not {"runA__recon.nii.gz", "runA__resources.json"} & hub.files          # replaced: gone
    assert {"runB__recon.nii.gz", "runB__resources.json"} <= hub.files             # only copy: kept
    assert by_id["runB"]["volumes"]["recon"] == PREFIX + "runB__recon.nii.gz"
    assert by_id["runB"]["volumes_stale"] is True
    assert f"{_bucket('runA')}runA__recon.nii.gz" in hub.files                     # the replacement


def test_a_clean_publish_deletes_the_flat_copies_it_replaced(tmp_path, monkeypatch):
    hub = FakeHub({"runA__recon.nii.gz", "runB__recon.nii.gz", "unrelated__recon.nii.gz"})
    rc, _, _ = _publish(tmp_path, monkeypatch, hub, "--prune")
    assert rc == 0
    assert not {"runA__recon.nii.gz", "runB__recon.nii.gz"} & hub.files
    assert "unrelated__recon.nii.gz" in hub.files       # the flat root is never judged by absence


def test_retired_runs_in_a_touched_bucket_go_only_after_a_clean_publish(tmp_path, monkeypatch):
    retired = f"{_bucket('runA')}retired__recon.nii.gz"      # same bucket as runA, in no index row
    hub = FakeHub({retired}, reject="runB")
    rc, _, _ = _publish(tmp_path, monkeypatch, hub, "--prune")
    assert rc == 2 and retired in hub.files                # a failed upload proves nothing about it
    hub.reject = ""
    rc = pv.main()                                          # same results dir, Hub healthy
    assert rc == 0 and retired not in hub.files


def test_without_prune_nothing_is_deleted(tmp_path, monkeypatch):
    hub = FakeHub({"runA__recon.nii.gz", f"{_bucket('runA')}retired__recon.nii.gz"})
    rc, _, _ = _publish(tmp_path, monkeypatch, hub)
    assert rc == 0 and {"runA__recon.nii.gz", f"{_bucket('runA')}retired__recon.nii.gz"} <= hub.files


def test_the_merge_job_prunes_and_squashes_after_a_full_rescore():
    wf = (ROOT / ".github" / "workflows" / "score.yml").read_text()
    assert "python scripts/publish_volumes.py results --prune" in wf
    squash = wf[wf.index("Squash HF volume history"):]
    assert "needs.plan.outputs.full == 'true'" in squash.split("run:")[0]
    assert "python scripts/squash_hf_history.py" in squash


def test_a_focused_rescore_never_deletes_another_runs_only_copy_in_a_bucket_it_touches(tmp_path, monkeypatch):
    """Retired-run cleanup runs in the buckets a clean publish wrote to, but liveness comes from the
    full index, not from what this results dir produced: a run this rescore did not touch keeps the
    one copy its row points at, while a file no row references any more goes."""
    bucket = _bucket("runA")
    other = f"{bucket}runC__recon.nii.gz"        # another run's only copy, sharing runA's bucket
    retired = f"{bucket}retired__recon.nii.gz"   # in no row at all
    hub = FakeHub({other, retired})
    row_c = {"id": "runC", "status": "ok", "phantom": "sim", "stage": "dipole",
             "volumes": {"recon": PREFIX + other}}
    rc, by_id, _ = _publish(tmp_path, monkeypatch, hub, "--prune", runs=("runA",), extra_rows=(row_c,))
    assert rc == 0
    assert other in hub.files and retired not in hub.files
    assert by_id["runC"]["volumes"]["recon"] == PREFIX + other      # its row is untouched


# ---- harmonization track: liveness is pipeline × acquisition, derived the way the viewer derives URLs --
# No index row names these files, so --prune-repro rebuilds the viewer's exact name set from
# repro.json and the acquisition registry. These pin that derivation (a drift here deletes live files).

ACQS = frozenset({"cima-bridge-run1", "prisma-local-run2"})
PIPES = ["romeo-qsmrs+vsharp-qsmrs+rts-qsmrs", "laplacian-qsmci+nextqsm", "iqsm"]
A = "repro/cima-bridge-run1/"


def test_repro_live_names_cover_every_kind_the_viewer_derives():
    live = pv.repro_live_names(PIPES, ACQS)
    assert A + "romeo-qsmrs_vsharp-qsmrs_rts-qsmrs-cmp-cima-bridge-run1__recon.nii.gz" in live
    assert A + "romeo-qsmrs_vsharp-qsmrs_rts-qsmrs-cmp-cima-bridge-run1__regions.json" in live
    assert A + "laplacian-qsmci_nextqsm-cmp-cima-bridge-run1__resources.json" in live
    assert A + "iqsm-cmp-cima-bridge-run1__recon.nii.gz" in live
    assert {A + "romeo-qsmrs__totalfield.nii.gz", A + "laplacian-qsmci__totalfield.nii.gz"} <= live
    assert A + "romeo-qsmrs_vsharp-qsmrs__localfield.nii.gz" in live
    assert not any("localfield" in n and "nextqsm" in n for n in live)   # a 2-part pipeline has no bfr column
    assert A + "cima-bridge-run1__magnitude.nii.gz" in live
    assert len(live) == 2 * (1 + 3 * 3 + 2 + 1)      # per acq: magnitude, 3 kinds × 3 pipes, 2 tf, 1 lf


SLUGS = frozenset({"romeo-qsmrs", "laplacian-qsmci", "vsharp-qsmrs", "rts-qsmrs", "nextqsm", "iqsm", "modip"})


def test_repro_orphans_split_retired_from_merely_unharvested():
    """Retired = no live pipeline names it AND it names a method outside the manifest. A file built
    only from live methods that repro.json lacks (no ROI stats yet) is the only copy: kept."""
    live = pv.repro_live_names(PIPES, ACQS)
    retired = [A + "romeo-qsmrs_msmv_rts-qsmrs-cmp-cima-bridge-run1__recon.nii.gz",   # msmv: gone
               A + "romeo-qsmrs_msmv__localfield.nii.gz"]                              # its column
    unharvested = [A + "romeo-qsmrs_vsharp-qsmrs_modip-cmp-cima-bridge-run1__recon.nii.gz",  # GPU run, no stats
                   A + "romeo-qsmrs_vsharp-qsmrs_modip-cmp-cima-bridge-run1__resources.json"]
    files = sorted(live) + retired + unharvested + [
        A + "x-cmp-cima-bridge-run1__novelkind.nii.gz",                # a kind this script does not know
        A + "README.md",                                               # not an artifact at all
        "repro/ghost-acq/iqsm-cmp-ghost-acq__recon.nii.gz",             # an acquisition the registry lacks
        "truth/sim/chimap.nii.gz", "runs/sim/ab/x__recon.nii.gz", "old__recon.nii.gz"]
    got_retired, got_unharvested, coverage, unknown = pv.repro_orphans(files, live, ACQS, SLUGS)
    assert got_retired == sorted(retired)
    assert got_unharvested == sorted(unharvested)
    assert unknown == {"ghost-acq"}
    assert coverage == len(live) / (len(live) + 4)


def test_repro_coverage_is_a_precondition_on_the_pipeline_list():
    live = pv.repro_live_names(["iqsm"], {"cima-bridge-run1"})
    files = sorted(live) + [f"{A}gone{i}-cmp-cima-bridge-run1__recon.nii.gz" for i in range(40)]
    _, _, coverage, _ = pv.repro_orphans(files, live, {"cima-bridge-run1"}, SLUGS)
    assert coverage < pv.FLAT_COVERAGE_MIN


def test_no_manifest_slug_contains_an_underscore():
    """--prune-repro reads methods off a file name as `_`-separated slugs; a slug with `_` would make
    a live method look retired. The script refuses in that case — and this makes the change loud."""
    slugs = pv.live_algo_slugs()
    assert slugs and not [s for s in slugs if "_" in s]


def test_the_real_repro_json_and_registry_derive_soundly():
    pipes = json.loads((ROOT / "results" / "repro.json").read_text())["pipelines"]
    acqs = pv.repro_acq_ids()
    assert len(acqs) == 23 and all(re.fullmatch(r"(prisma|cima)-.+-run\d", a) for a in acqs)
    assert pipes and all(1 <= len(p.split("+")) <= 3 and "_" not in p and "~" not in p for p in pipes)
    assert len(pv.repro_live_names(pipes, acqs)) > 3 * len(pipes) * len(acqs)
    assert all(m in pv.live_algo_slugs() for p in pipes for m in p.split("+"))   # fits already drops retired


def _prune_repro(tmp_path, monkeypatch, hub, pipelines, *argv, slugs=SLUGS):
    results = tmp_path / "results"; results.mkdir(exist_ok=True)
    (results / "repro.json").write_text(json.dumps({"target": "cima-bridge-run1",
                                                    "pipelines": {p: {} for p in pipelines}}))
    fake = SimpleNamespace(HfApi=lambda token=None: hub,
                           CommitOperationAdd=lambda path_in_repo, path_or_fileobj:
                           SimpleNamespace(path_in_repo=path_in_repo, path_or_fileobj=path_or_fileobj))
    monkeypatch.setitem(sys.modules, "huggingface_hub", fake)
    monkeypatch.setattr(pv, "repro_acq_ids", lambda: ACQS)
    monkeypatch.setattr(pv, "live_algo_slugs", lambda: slugs)
    monkeypatch.setattr(pv.time, "sleep", lambda s: None)
    monkeypatch.setenv("HF_VOLUMES_REPO", REPO)
    monkeypatch.setenv("HF_TOKEN", "t")
    monkeypatch.setattr(sys, "argv", ["publish_volumes.py", str(results), "--prune-repro", *argv])
    return pv.main()


RETIRED = A + "romeo-qsmrs_msmv_rts-qsmrs-cmp-cima-bridge-run1__recon.nii.gz"


UNHARVESTED = A + "romeo-qsmrs_vsharp-qsmrs_modip-cmp-cima-bridge-run1__recon.nii.gz"


def test_prune_repro_deletes_retired_pipelines_and_keeps_every_live_or_unharvested_file(tmp_path, monkeypatch):
    live = pv.repro_live_names(PIPES, ACQS)
    hub = FakeHub(live | {RETIRED, UNHARVESTED, "repro/ghost-acq/iqsm-cmp-ghost-acq__recon.nii.gz",
                          "old__recon.nii.gz"})
    assert _prune_repro(tmp_path, monkeypatch, hub, PIPES) == 0
    assert RETIRED not in hub.files
    assert live <= hub.files                                            # nothing live touched
    assert UNHARVESTED in hub.files                                     # live methods, no stats yet: the only copy
    assert {"repro/ghost-acq/iqsm-cmp-ghost-acq__recon.nii.gz", "old__recon.nii.gz"} <= hub.files


def test_prune_repro_refuses_without_a_manifest_to_judge_retirement_by(tmp_path, monkeypatch):
    """No manifest means every method looks retired; the script must refuse rather than delete."""
    before = pv.repro_live_names(PIPES, ACQS) | {RETIRED}
    hub = FakeHub(before)
    assert _prune_repro(tmp_path, monkeypatch, hub, PIPES, slugs=frozenset()) == 0
    assert hub.files == before
    hub = FakeHub(before)                                       # and a slug with '_' is unparseable
    assert _prune_repro(tmp_path, monkeypatch, hub, PIPES, slugs=SLUGS | {"bad_slug"}) == 0
    assert hub.files == before


def test_prune_repro_dry_run_deletes_nothing(tmp_path, monkeypatch):
    hub = FakeHub(pv.repro_live_names(PIPES, ACQS) | {RETIRED})
    assert _prune_repro(tmp_path, monkeypatch, hub, PIPES, "--prune-dry-run") == 0
    assert RETIRED in hub.files


def test_prune_repro_refuses_an_empty_or_unrepresentative_pipeline_list(tmp_path, monkeypatch):
    before = pv.repro_live_names(PIPES, ACQS) | {RETIRED}
    hub = FakeHub(before)
    _prune_repro(tmp_path, monkeypatch, hub, [])                      # no pipelines ≠ all retired
    assert hub.files == before
    hub = FakeHub(before)
    _prune_repro(tmp_path, monkeypatch, hub, ["iqsm"])                # explains too little of the repo
    assert hub.files == before


def test_repro_evaluate_prunes_and_both_squashes_wait_for_the_other_writer():
    repro = (ROOT / ".github" / "workflows" / "repro.yml").read_text()
    assert "python scripts/publish_volumes.py --prune-repro" in repro
    # the manual entry point (repro.yml is dispatch-only, so retirement can wait a long time otherwise)
    hk = (ROOT / ".github" / "workflows" / "hf-housekeeping.yml").read_text()
    assert "--prune-repro" in hk and "squash_hf_history.py" in hk
    assert "for wf in score.yml repro.yml" in hk and "--status in_progress" in hk   # never overlap a publisher
    assert not (ROOT / ".github" / "workflows" / "squash-volumes.yml").exists()
    for wf, other in (("score.yml", "repro.yml"), ("repro.yml", "score.yml")):
        txt = (ROOT / ".github" / "workflows" / wf).read_text()
        squash = txt[txt.index("- name: Squash HF volume history"):]
        # score.yml's scope lives in its `plan` job (scripts/score_plan.py); repro.yml keeps `scope`.
        planner = "plan" if wf == "score.yml" else "scope"
        assert f"needs.{planner}.outputs.full == 'true'" in squash.split("run:")[0]
        assert f"gh run list --workflow {other} --status in_progress" in squash
        assert "actions: read" in txt
