"""Each phantom's ground truth gets its own Hub path.

Every registered dataset lives at data/<phantom>/scoring, and pipeline.py used to stage a truth
under the dataset dir's own name, so every phantom's truth was published to truth/scoring/<artifact>.
The χ-separation phantoms all have a chi-para / chi-dia, so each publish overwrote the others' and
the viewer showed whichever phantom published last (and the in-vivo chimap collided with the
in-silico one). These pin the wiring: the truth.ref pointer emit_volumes writes, and the Hub name
publish_volumes derives from it, carry the phantom's registry key, the same for every input level.
"""
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


pv = _load("publish_volumes")

PHANTOMS = {  # key -> track, laid out as the real registry: data/<key>/scoring
    "sim": "sim", "invivo": "invivo", "meso-3t": "chisep", "wm-micro-7t": "chisep",
    "ridani-3t-aniso-fitted": "chisep",
}


def _nii(path: Path, seed: int):
    import nibabel as nib
    import numpy as np
    path.parent.mkdir(parents=True, exist_ok=True)
    data = np.random.default_rng(seed).normal(size=(4, 4, 4)).astype("float32")
    nib.save(nib.Nifti1Image(data, np.eye(4)), str(path))


@pytest.fixture
def pipeline(tmp_path, monkeypatch):
    reg = {k: {"track": t, "label": k, "path": f"data/{k}/scoring", "active": True,
               "default": k in ("sim", "invivo", "meso-3t")} for k, t in PHANTOMS.items()}
    (tmp_path / "reg.json").write_text(json.dumps(reg))
    monkeypatch.setenv("QSMCI_DATASETS_FILE", str(tmp_path / "reg.json"))
    mod = _load("pipeline")
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    return mod


def _emit(pipeline, tmp_path, rid, truth, seed):
    recon, mask = tmp_path / "recon.nii.gz", tmp_path / "mask.nii.gz"
    _nii(recon, 100 + seed)
    _nii(mask, 200 + seed)
    pipeline.emit_volumes(rid, recon, truth, mask)
    results = tmp_path / "results"
    return pv.resolve_truth(results / rid, results, {"stage": "chi-separation"}, "truth")


def test_chisep_phantoms_publish_their_truth_to_distinct_paths(pipeline, tmp_path):
    names = {}
    for i, ph in enumerate(("meso-3t", "wm-micro-7t", "ridani-3t-aniso-fitted")):
        truth = tmp_path / "data" / ph / "scoring" / "groundtruth" / "chi-para.nii.gz"
        _nii(truth, i)
        path, name = _emit(pipeline, tmp_path, f"m-iso-{ph}", truth, i)
        assert name == f"truth/{ph}/chi-para.nii.gz"
        assert path.read_bytes() == truth.read_bytes()   # no phantom's staged copy was overwritten
        names[ph] = name
    assert len(set(names.values())) == 3


def test_truth_path_is_the_same_for_every_input_level(pipeline, tmp_path):
    """gt and l3 runs score against the one groundtruth/ dir; a truth staged from inputs/ (the
    generated-R2′ reference) lands in the same phantom directory."""
    ds = tmp_path / "data" / "wm-micro-7t" / "scoring"
    _nii(ds / "groundtruth" / "chi-dia.nii.gz", 1)
    _nii(ds / "inputs" / "r2prime.nii.gz", 2)
    _, gt = _emit(pipeline, tmp_path, "m-iso-wm-micro-7t", ds / "groundtruth" / "chi-dia.nii.gz", 1)
    _, l3 = _emit(pipeline, tmp_path, "m-iso-wm-micro-7t-l3", ds / "groundtruth" / "chi-dia.nii.gz", 1)
    _, r2 = _emit(pipeline, tmp_path, "g-iso-wm-micro-7t", ds / "inputs" / "r2prime.nii.gz", 2)
    assert gt == l3 == "truth/wm-micro-7t/chi-dia.nii.gz"
    assert r2 == "truth/wm-micro-7t/r2prime.nii.gz"


def test_insilico_and_invivo_truths_no_longer_share_a_path(pipeline, tmp_path):
    sim = tmp_path / "data" / "sim" / "scoring" / "groundtruth" / "chimap.nii.gz"
    inv = tmp_path / "data" / "invivo" / "scoring" / "groundtruth" / "chimap.nii.gz"
    _nii(sim, 1)
    _nii(inv, 2)
    results = tmp_path / "results"
    pipeline.emit_volumes("a-iso", sim, sim, sim)
    pipeline.emit_volumes("a-iso-invivo", inv, inv, inv)
    _, sim_name = pv.resolve_truth(results / "a-iso", results, {"stage": "dipole"}, "truth")
    _, inv_name = pv.resolve_truth(results / "a-iso-invivo", results, {"stage": "dipole"}, "truth")
    # the paths the legacy per-run truths were already folded into on the Hub
    assert sim_name == "truth/sim/chimap.nii.gz" == pv.truth_name({"stage": "dipole", "phantom": "sim"}, "truth")
    assert inv_name == "truth/invivo/chimap.nii.gz" == pv.truth_name({"stage": "dipole", "phantom": "invivo"}, "truth")


def test_unregistered_dataset_keeps_its_directory_name(pipeline, tmp_path):
    truth = tmp_path / "data" / "sim" / "dev" / "groundtruth" / "chimap.nii.gz"
    assert pipeline.truth_phantom(truth) == "dev"


def test_every_registered_scoring_phantom_has_its_own_truth_dir(monkeypatch):
    """The real registry: each scored (non-harmonization) phantom maps back to its own key."""
    monkeypatch.delenv("QSMCI_DATASETS_FILE", raising=False)
    pipeline = _load("pipeline")
    reg = pipeline.load_datasets()
    for key, entry in reg.items():
        if entry.get("track") == "repro":
            continue
        truth = ROOT / entry["path"] / "groundtruth" / "chi-para.nii.gz"
        assert pipeline.truth_phantom(truth) == key
