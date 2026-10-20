"""The per-echo QSM input (`chimap-echoes`): one χ map per echo, which DECOMPOSE-QSM is defined on.

It is outside every stage contract and only some χ-separation phantoms ship it, so a method opts in
with `optional_inputs: [chimap-echoes]` and every layer — the CLI parser, the mount, the scorer's
argv and its input staging — must pass it through when it exists and carry on without it when it
does not.
"""
from pathlib import Path

import nibabel as nib
import numpy as np
import yaml

from qsm_ci import runner
from qsm_ci.stages import ARTIFACT_FILE as AF
from scoring import cli_run_argv, gt_sources

ROOT = Path(__file__).resolve().parent.parent


def _manifest(slug):
    algo = yaml.safe_load((ROOT / "algorithms" / slug / "algorithm.yml").read_text())
    return {**algo, "slug": slug, "dir": ROOT / "algorithms" / slug}


def test_both_decompose_entries_opt_in_and_keep_it_optional():
    for slug in ("decompose-qsmrs", "decompose-qsm"):
        algo = _manifest(slug)
        assert "chimap-echoes" in runner._consumes(algo), slug
        parser = runner._build_run_parser(slug, algo)
        action = next(a for a in parser._actions if a.dest == "chimap_echoes")
        assert not action.required, f"{slug}: a phantom without it must still run"
        assert action.nargs == "+", "one 4D file or per-echo 3D files, like the magnitude"


def test_scorer_passes_it_only_when_the_dataset_has_it(tmp_path):
    algo = {"stage": "chi-separation", "dir": Path("/algos/decompose-qsmrs"),
            "consumes": runner._consumes(_manifest("decompose-qsmrs")), "produces": ["chi-para", "chi-dia"]}
    assert "--chimap-echoes" not in cli_run_argv(algo, tmp_path, Path("/out"), AF)
    (tmp_path / "chimap-echoes.nii.gz").write_text("x")
    argv = cli_run_argv(algo, tmp_path, Path("/out"), AF)
    i = argv.index("--chimap-echoes")
    assert argv[i + 1] == str(tmp_path / "chimap-echoes.nii.gz")


def test_it_is_sourced_from_the_phantom_inputs(tmp_path):
    (tmp_path / "inputs").mkdir()
    (tmp_path / "inputs" / "chimap-echoes.nii.gz").write_text("x")
    assert gt_sources(tmp_path)["chimap-echoes"] == tmp_path / "inputs" / "chimap-echoes.nii.gz"


def test_staging_skips_it_when_absent_and_copies_it_when_present(tmp_path, pipeline):
    src = tmp_path / "src"
    src.mkdir()
    for f in ("chimap.nii.gz", "mask.nii.gz"):
        (src / f).write_text("x")
    sources = {"chimap": src / "chimap.nii.gz", "mask": src / "mask.nii.gz",
               "chimap-echoes": src / "chimap-echoes.nii.gz"}
    dest = tmp_path / "in"
    pipeline.prepare_input(["chimap", "chimap-echoes", "mask"], sources, dest)
    assert sorted(p.name for p in dest.iterdir()) == ["chimap.nii.gz", "mask.nii.gz"]
    (src / "chimap-echoes.nii.gz").write_text("x")
    pipeline.prepare_input(["chimap", "chimap-echoes", "mask"], sources, dest)
    assert (dest / "chimap-echoes.nii.gz").exists()


def test_the_cli_mounts_it_for_an_opted_in_method(tmp_path):
    """End to end on the `local` runner: --chimap-echoes reaches the method's /input as a 4D file."""
    method = tmp_path / "echo-method"
    method.mkdir()
    (method / "algorithm.yml").write_text(
        "name: Echo\nslug: echo-method\nstage: chi-separation\n"
        "inputs: [chimap, magnitude, mask, params]\noptional_inputs: [chimap-echoes]\n"
        "image: bash:latest\nrun: bash run.sh\n")
    (method / "run.sh").write_text(
        '#!/usr/bin/env bash\nset -euo pipefail\nIN="${1:-/input}"; OUT="${2:-/output}"\n'
        '[ -f "$IN/chimap-echoes.nii.gz" ] || { echo "chimap-echoes was not mounted" >&2; exit 3; }\n'
        'cp "$IN/chimap.nii.gz" "$OUT/chi-para.nii.gz"; cp "$IN/chimap.nii.gz" "$OUT/chi-dia.nii.gz"\n')
    save = lambda name, shape: nib.save(nib.Nifti1Image(np.ones(shape, "float32"), np.eye(4)),
                                        str(tmp_path / name))
    save("chimap.nii.gz", (4, 4, 4))
    save("mask.nii.gz", (4, 4, 4))
    save("magnitude.nii.gz", (4, 4, 4, 3))
    save("chimap-echoes.nii.gz", (4, 4, 4, 3))
    (tmp_path / "p.json").write_text('{"TE": [0.004, 0.008, 0.012], "B0": 3.0, "B0_dir": [0, 0, 1], '
                                     '"voxel_size": [1, 1, 1]}')
    out = tmp_path / "out"
    rc = runner.run_command([str(method),
                             "--chimap", str(tmp_path / "chimap.nii.gz"),
                             "--chimap-echoes", str(tmp_path / "chimap-echoes.nii.gz"),
                             "--magnitude", str(tmp_path / "magnitude.nii.gz"),
                             "--mask", str(tmp_path / "mask.nii.gz"),
                             "--params", str(tmp_path / "p.json"),
                             "--runner", "local", "-o", str(out) + "/"])
    assert rc == 0
    assert (out / "chi-para.nii.gz").exists()
