"""The phantom's segmentation (`dseg`) is mountable, but only into a baseline.

ridani-null-qsmci is built to solve white matter separately from the segmentation, but `dseg` was not
a canonical artifact, so `runner._consumes` dropped it and the scorer never mounted it: the baseline
only ever ran its no-segmentation fallback. `dseg` is now an artifact that a method marked
`baseline: true` may opt into (stages.yml `baseline_only`), and any other method that names it is
refused, so a method scored for its own skill can't be handed ground-truth anatomy. Wiring only.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from qsm_ci import runner
from scoring import cli_run_argv, gt_sources
from qsm_ci.stages import ARTIFACT_FILE

ROOT = Path(__file__).resolve().parent.parent

BASELINE = {"stage": "chi-separation", "slug": "a-baseline", "baseline": True,
            "inputs": ["chimap", "r2prime", "mask", "params"], "optional_inputs": ["dseg"]}


@pytest.mark.parametrize("decl", [{"optional_inputs": ["dseg"]},
                                  {"inputs": ["chimap", "r2prime", "mask", "params", "dseg"]}])
@pytest.mark.parametrize("flag", [None, False, "true"])
def test_a_non_baseline_naming_dseg_is_refused(decl, flag):
    algo = {"stage": "chi-separation", "slug": "a-method", **decl}
    if flag is not None:
        algo["baseline"] = flag
    with pytest.raises(SystemExit, match="only a baseline"):
        runner._consumes(algo)


def test_a_baseline_gets_dseg_as_an_optional_input():
    assert "dseg" in runner._consumes(BASELINE)
    assert runner._optional(BASELINE, "dseg")
    parser = runner._build_run_parser("a-baseline", {**BASELINE, "name": "A baseline"})
    flags = {a.dest: a for a in parser._actions}
    assert "dseg" in flags and not flags["dseg"].required


def test_no_other_method_is_offered_a_dseg_flag():
    algo = {"stage": "chi-separation", "slug": "a-method", "name": "A method",
            "inputs": ["chimap", "r2prime", "mask", "params"]}
    assert "dseg" not in runner._accepts(algo)


def test_ridani_null_declares_dseg_as_a_baseline():
    doc = yaml.safe_load((ROOT / "algorithms" / "ridani-null-qsmci" / "algorithm.yml").read_text())
    assert doc["baseline"] is True
    assert "dseg" in runner._consumes(doc) and runner._optional(doc, "dseg")


def test_scorer_mounts_dseg_when_the_dataset_has_it(pipeline, tmp_path):
    ds = tmp_path / "ds"
    for sub in ("inputs", "groundtruth"):
        (ds / sub).mkdir(parents=True)
    for f in ("chimap.nii.gz", "r2prime.nii.gz", "mask.nii.gz"):
        (ds / "inputs" / f).write_bytes(b"x")
    (ds / "inputs" / "params.json").write_text(json.dumps({"B0": 3}))
    src = gt_sources(ds)
    assert src["dseg"] == ds / "groundtruth" / "dseg.nii.gz"   # falls back to groundtruth/

    algo = {**BASELINE, "dir": Path("/algo"), "produces": ["chi-para", "chi-dia"],
            "consumes": runner._consumes(BASELINE), "optional": ["dseg"]}
    # Absent from the dataset: skipped, not a FileNotFoundError, and no --dseg flag.
    idir = tmp_path / "in"
    pipeline.prepare_input(algo["consumes"], src, idir, algo["optional"])
    assert not (idir / "dseg.nii.gz").exists()
    assert "--dseg" not in cli_run_argv(algo, idir, tmp_path / "out", ARTIFACT_FILE)
    # Present: mounted under its canonical name and passed.
    (ds / "groundtruth" / "dseg.nii.gz").write_bytes(b"seg")
    pipeline.prepare_input(algo["consumes"], src, idir, algo["optional"])
    assert (idir / "dseg.nii.gz").read_bytes() == b"seg"
    assert "--dseg" in cli_run_argv(algo, idir, tmp_path / "out", ARTIFACT_FILE)
    # A required artifact still fails loudly when missing.
    with pytest.raises(FileNotFoundError):
        pipeline.prepare_input(["localfield"], src, idir)


def test_discovery_carries_the_optional_list(pipeline):
    algos = {a["slug"]: a for a in pipeline.discover_algorithms(track="chisep")}
    assert algos["ridani-null-qsmci"]["optional"] == ["dseg"]
    assert all("dseg" not in a["consumes"] for s, a in algos.items() if s != "ridani-null-qsmci")
