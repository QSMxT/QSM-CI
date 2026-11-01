"""Realistic χ-separation inputs (L3): packed, planned, mounted, namespaced. Wiring only.

qsm-forward's controlled-degradation level L3 (qsm_forward.degrade) is calibrated to real QSM
pipelines; its physics is tested in qsm-forward. Here: pack_dataset.py ships it as inputs-l3/
beside the untouched ground-truth inputs, gen_chisep_preset.py asks the generator for it and zips it,
score_plan.py plans a separate isolated job for it, and pipeline.py --inputs l3 mounts it in place of
the five derived artifacts, scores on the dataset's brain mask, and namespaces the rows. Tiny volumes
and a fixture method on the container-free local runner.
"""
from __future__ import annotations

import importlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import nibabel as nib
import numpy as np
import pytest

from qsm_ci import qsm_eval
from scoring import LEVEL_ARTIFACTS, gt_sources, inputs_suffix, level_sources

ROOT = Path(__file__).resolve().parent.parent
TE = [0.004, 0.008, 0.012]
SHAPE = (12, 12, 12)


def _save(path: Path, arr, dtype="float32") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    nib.save(nib.Nifti1Image(np.asarray(arr, dtype), np.eye(4)), str(path))


def _touch_dataset(ds: Path, l3: bool = True, echoes: bool = False) -> None:
    for f in ("phase", "magnitude", "mask", "localfield", "chimap", "r2prime", "dseg"):
        (ds / "inputs").mkdir(parents=True, exist_ok=True)
        (ds / "inputs" / f"{f}.nii.gz").write_bytes(b"gt")
    (ds / "inputs" / "params.json").write_text("{}")
    (ds / "inputs" / "chimap-echoes.nii.gz").write_bytes(b"gt")
    (ds / "groundtruth").mkdir(exist_ok=True)
    if l3:
        (ds / "inputs-l3").mkdir()
        for f in ("localfield", "chimap", "r2prime", "mask"):
            (ds / "inputs-l3" / f"{f}.nii.gz").write_bytes(b"l3")
        if echoes:
            (ds / "inputs-l3" / "chimap-echoes.nii.gz").write_bytes(b"l3")


# --------------------------------------------------------------------------------- source map

def test_level_sources_swaps_exactly_the_derived_artifacts(tmp_path):
    ds = tmp_path / "ds"
    _touch_dataset(ds, echoes=True)
    assert level_sources(ds, "gt") == gt_sources(ds)
    src = level_sources(ds, "l3")
    for art, path in src.items():
        want = "inputs-l3" if art in LEVEL_ARTIFACTS else ("inputs" if (ds / "inputs" / path.name).exists()
                                                           else "groundtruth")
        assert path.parent.name == want, art
    # the raw signal, params and the (baseline-only) segmentation are shared by every level
    assert src["phase"] == ds / "inputs" / "phase.nii.gz" and src["dseg"] == ds / "inputs" / "dseg.nii.gz"
    assert inputs_suffix("gt") == "" and inputs_suffix("l3") == "-l3"


def test_a_level_without_chimap_echoes_never_falls_back_to_the_ground_truth(tmp_path):
    ds = tmp_path / "ds"
    _touch_dataset(ds, echoes=False)
    src = level_sources(ds, "l3")
    assert src["chimap-echoes"] == ds / "inputs-l3" / "chimap-echoes.nii.gz"
    assert not src["chimap-echoes"].exists()   # absent → the optional input is skipped


def test_level_sources_refuses_a_zip_without_the_level(tmp_path):
    ds = tmp_path / "ds"
    _touch_dataset(ds, l3=False)
    with pytest.raises(SystemExit, match="no inputs-l3"):
        level_sources(ds, "l3")
    _touch_dataset(tmp_path / "ds2")
    (tmp_path / "ds2" / "inputs-l3" / "r2prime.nii.gz").unlink()
    with pytest.raises(SystemExit, match="missing r2prime"):
        level_sources(tmp_path / "ds2", "l3")


# --------------------------------------------------------------------------------- packing

def _bids(tmp_path: Path) -> Path:
    bids = tmp_path / "bids"
    anat = bids / "sub-1" / "anat"
    der = bids / "derivatives" / "qsm-forward" / "sub-1" / "anat"
    for e, te in enumerate(TE, 1):
        for part in ("mag", "phase"):
            _save(anat / f"sub-1_echo-{e}_part-{part}_MEGRE.nii", np.ones(SHAPE))
        (anat / f"sub-1_echo-{e}_part-phase_MEGRE.json").write_text(
            json.dumps({"EchoTime": te, "MagneticFieldStrength": 3.0}))
    gt = {"Chimap": 0.1, "Chimap-pos": 0.2, "Chimap-neg": 0.3, "mask": 1, "fieldmap-local": 0.4, "R2prime": 5}
    for name, v in gt.items():
        _save(der / f"sub-1_{name}.nii", np.full(SHAPE, v))
    # L3 files sort BEFORE the ground truth (`sub-1_desc-…` < `sub-1_mask`) and share its suffixes
    l3 = {"Chimap": 0.11, "fieldmap-local": 0.41, "R2prime": 6, "mask": 1,
          "Chimap-echoes": np.full(SHAPE + (len(TE),), 0.12)}
    for name, v in l3.items():
        _save(der / f"sub-1_desc-degradedL3_{name}.nii", np.full(SHAPE, v) if np.isscalar(v) else v,
              "uint8" if name == "mask" else "float32")
    (der / "sub-1_desc-degradedL3_degradation.json").write_text(json.dumps({"DegradationLevel": "L3"}))
    return bids


def test_pack_dataset_ships_l3_beside_the_unchanged_inputs(tmp_path):
    out = tmp_path / "packed"
    subprocess.run([sys.executable, str(ROOT / "scripts" / "pack_dataset.py"), str(_bids(tmp_path)),
                    str(out), "--chisep"], check=True, capture_output=True, text=True)
    val = lambda rel: float(np.unique(nib.load(str(out / rel)).get_fdata())[0])
    # ground-truth inputs are the phantom's own maps, not the degraded ones
    assert val("inputs/chimap.nii.gz") == pytest.approx(0.1) and val("inputs/localfield.nii.gz") == pytest.approx(0.4)
    assert val("inputs/r2prime.nii.gz") == 5 and not (out / "inputs" / "chimap-echoes.nii.gz").exists()
    assert val("groundtruth/chimap.nii.gz") == pytest.approx(0.1)
    # L3 under inputs-l3/, canonical names
    assert sorted(p.name for p in (out / "inputs-l3").iterdir()) == sorted(f"{a}.nii.gz" for a in LEVEL_ARTIFACTS)
    assert val("inputs-l3/chimap.nii.gz") == pytest.approx(0.11) and val("inputs-l3/r2prime.nii.gz") == 6
    assert nib.load(str(out / "inputs-l3" / "chimap-echoes.nii.gz")).shape == SHAPE + (len(TE),)
    assert json.loads((out / "groundtruth" / "degradation-l3.json").read_text())["DegradationLevel"] == "L3"


# --------------------------------------------------------------------------------- generator

def test_registry_asks_for_l3_exactly_where_it_lists_the_level():
    gcp = importlib.import_module("gen_chisep_preset")
    reg = json.loads((ROOT / "scripts" / "datasets.json").read_text())
    for k, d in reg.items():
        g = d.get("generator") or {}
        assert ("L3" in g.get("degrade_levels", [])) == ("l3" in d.get("input_levels", [])), k
        if g.get("degrade_levels"):
            assert gcp.preset_overrides(g)["degrade_levels"] == ("L3",)   # ChisepConfig wants a tuple
    assert any("l3" in d.get("input_levels", []) for d in reg.values() if d.get("default"))


@pytest.mark.skipif(shutil.which("zip") is None, reason="make_zip shells out to zip")
def test_make_zip_includes_the_level_directories(tmp_path):
    gcp = importlib.import_module("gen_chisep_preset")
    out = tmp_path / "meso"
    for rel in ("inputs/mask.nii.gz", "groundtruth/chi-para.nii.gz", "inputs-l3/mask.nii.gz"):
        (out / rel).parent.mkdir(parents=True, exist_ok=True)
        (out / rel).write_bytes(b"x")
    import zipfile
    names = zipfile.ZipFile(gcp.make_zip(out)).namelist()
    assert {"inputs/mask.nii.gz", "groundtruth/chi-para.nii.gz", "inputs-l3/mask.nii.gz"} <= set(names)


# --------------------------------------------------------------------------------- planner

def _score_plan():
    spec = importlib.util.spec_from_file_location("score_plan", ROOT / "scripts" / "score_plan.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


REG = {"sim": {"track": "sim", "active": True, "default": True},
       "invivo": {"track": "invivo", "active": True, "default": True},
       "meso": {"track": "chisep", "active": True, "default": True, "input_levels": ["l3"]},
       "plain": {"track": "chisep", "active": True, "default": False}}


def test_planner_adds_one_isolated_l3_job_per_listed_phantom(tmp_path):
    sp = _score_plan()
    root = tmp_path / "algorithms"
    for slug, body in {"chi": "stage: chi-separation\nimage: x\n",
                       "gen": "stage: r2prime-generation\nimage: x\n"}.items():
        (root / slug).mkdir(parents=True)
        (root / slug / "algorithm.yml").write_text(body)
    t = {x["id"]: x for x in sp.plan_tasks(root, REG, full=True, slugs=[])}
    assert {"f-chi", "f-chi-l3", "f-chi-plain", "f-gen", "f-gen-plain"} <= set(t)
    assert "f-chi-plain-l3" not in t and "f-gen-l3" not in t     # not listed / not a χ-sep method
    assert t["f-chi-l3"]["inputs"] == "l3" and t["f-chi-l3"]["mode"] == "isolated"
    assert t["f-chi-l3"]["focus"] == "chi" and t["f-chi-l3"]["phantom"] == "meso"
    assert "inputs" not in t["f-chi"]
    # a changed R2′ generator re-plans the GRE-only combos, which have no degraded-input runs
    ids = {x["id"] for x in sp.plan_tasks(root, REG, full=False, slugs=["gen"])}
    assert "f-chi" in ids and "f-chi-l3" not in ids
    assert "f-chi-l3" in {x["id"] for x in sp.plan_tasks(root, REG, full=False, slugs=["chi"])}


def test_score_workflow_passes_the_task_input_level():
    wf = (ROOT / ".github" / "workflows" / "score.yml").read_text()
    assert "INPUTS: ${{ matrix.task.inputs }}" in wf and '--inputs $INPUTS' in wf


# --------------------------------------------------------------------------------- scorer

def _chisep_dataset(ds: Path) -> dict:
    rng = np.random.default_rng(1)
    mask = np.zeros(SHAPE)
    mask[2:10, 2:10, 2:10] = 1
    l3mask = np.zeros(SHAPE)
    l3mask[3:9, 3:9, 3:9] = 1                     # eroded
    v = {"para": rng.random(SHAPE) * 0.1, "dia": rng.random(SHAPE) * 0.05}
    v["chimap"] = v["para"] - v["dia"]
    v["chimap_l3"] = (v["chimap"] + rng.standard_normal(SHAPE) * 0.02) * l3mask
    v["mask"], v["l3mask"] = mask, l3mask
    _save(ds / "inputs" / "mask.nii.gz", mask)
    (ds / "inputs" / "params.json").write_text(json.dumps({"TE": TE, "B0": 3.0, "B0_dir": [0, 0, 1],
                                                           "voxel_size": [1, 1, 1]}))
    for f in ("localfield", "r2prime"):
        _save(ds / "inputs" / f"{f}.nii.gz", np.zeros(SHAPE))
        _save(ds / "inputs-l3" / f"{f}.nii.gz", np.ones(SHAPE) * l3mask)
    _save(ds / "inputs" / "chimap.nii.gz", v["chimap"])
    _save(ds / "inputs-l3" / "chimap.nii.gz", v["chimap_l3"])
    _save(ds / "inputs-l3" / "mask.nii.gz", l3mask, "uint8")
    _save(ds / "groundtruth" / "chi-para.nii.gz", v["para"])
    _save(ds / "groundtruth" / "chi-dia.nii.gz", v["dia"])
    return v


def _method(root: Path) -> None:
    d = root / "cp-chisep"
    d.mkdir(parents=True)
    (d / "algorithm.yml").write_text("name: CP chisep\nslug: cp-chisep\nstage: chi-separation\n"
                                     "inputs: [chimap, localfield, r2prime, mask, params]\n"
                                     "image: bash:latest\nrun: bash run.sh\n")
    (d / "run.sh").write_text('#!/usr/bin/env bash\nset -euo pipefail\nIN="${1:-/input}"; OUT="${2:-/output}"\n'
                              'cp "$IN/chimap.nii.gz" "$OUT/chi-para.nii.gz"\n'
                              'cp "$IN/chimap.nii.gz" "$OUT/chi-dia.nii.gz"\n')


@pytest.mark.parametrize("level", ["gt", "l3"])
def test_pipeline_inputs_level_end_to_end(tmp_path, level):
    v = _chisep_dataset(tmp_path / "ds")
    _method(tmp_path / "algos")
    reg = {"chisep-fx": {"track": "chisep", "label": "fx", "osf_file": "x", "path": "x", "active": True,
                         "default": False, "input_levels": ["l3"]}}
    (tmp_path / "reg.json").write_text(json.dumps(reg))
    env = {**os.environ, "QSMCI_ALGORITHMS_DIR": str(tmp_path / "algos"),
           "QSMCI_DATASETS_FILE": str(tmp_path / "reg.json")}
    work = tmp_path / "work"
    subprocess.run([sys.executable, str(ROOT / "scripts" / "pipeline.py"), "--dataset", str(tmp_path / "ds"),
                    "--phantom", "chisep-fx", "--mode", "both", "--runner", "local", "--track", "sim",
                    "--inputs", level, "--runs-out", str(tmp_path / "runs.json"), "--work", str(work)],
                   cwd=str(ROOT), env=env, check=True, capture_output=True, text=True)
    runs = json.loads((tmp_path / "runs.json").read_text())
    assert len(runs) == 1
    r = runs[0]
    sfx = "-chisep-fx" + ("-l3" if level == "l3" else "")
    assert r["id"] == f"cp-chisep-iso{sfx}" and r["status"] == "ok" and r["mode"] == "isolated"
    assert r.get("inputs") == (None if level == "gt" else "l3")
    # the method was handed the level's maps (and mask) …
    idir = work / f"iso_cp-chisep{sfx}_in"
    src = tmp_path / "ds" / ("inputs-l3" if level == "l3" else "inputs")
    for f in ("chimap", "mask", "localfield", "r2prime"):
        assert (idir / f"{f}.nii.gz").read_bytes() == (src / f"{f}.nii.gz").read_bytes(), f
    # … and is scored over the dataset's brain mask at either level, so the two are comparable
    chi = v["chimap_l3"] if level == "l3" else v["chimap"]
    want = qsm_eval.correlation(chi.astype("float32"), v["para"].astype("float32"), v["mask"])
    assert r["metrics"]["para_correlation"] == pytest.approx(want, abs=1e-5)


def test_pipeline_refuses_l3_off_the_chisep_track(tmp_path):
    out = subprocess.run([sys.executable, str(ROOT / "scripts" / "pipeline.py"), "--dataset", str(tmp_path),
                          "--inputs", "l3", "--runner", "local"], cwd=str(ROOT), capture_output=True, text=True)
    assert out.returncode != 0 and "χ-separation phantoms only" in out.stderr
