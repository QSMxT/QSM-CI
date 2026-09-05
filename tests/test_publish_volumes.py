"""Ground truth reaches the Hugging Face volumes repo ONCE per (phantom, artifact), never once per run.

publish_volumes.py used to upload `<run-id>__truth.nii.gz` for every scored run — hundreds of
byte-identical copies of each phantom's χ map. These pin the sharing rules: the Hub path is derived
from the phantom and the artifact the run's last stage produces, identical bytes collapse to one
upload, different bytes for the same name never overwrite each other, and both the new `truth.ref`
pointer pipeline.py writes and a legacy per-run `truth.nii.gz` resolve to the shared name.
"""
import importlib.util
from pathlib import Path

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
