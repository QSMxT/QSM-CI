"""Unit tests for the shared scoring/sweep primitives in qsm_ci.scoring.

These cover the PURE helpers only — no Docker, no dataset, no scientific stack. They pin the exact
argv/mapping/partition behaviour the three scripts (pipeline.py, sweep.py, combo_sweep.py) used to
each keep an inline copy of, so a future edit that changes what the scorer runs fails here loudly.
"""
from pathlib import Path

import pytest

from qsm_ci.scoring import (
    cli_run_argv, eval_argv, gt_sources, parse_shard, shard_owns, shard_partition,
)
from qsm_ci.stages import ARTIFACT_FILE as AF


# ---------------------------------------------------------------- cli_run_argv


def _algo(stage, consumes, produces, dir="/algos/x"):
    return {"stage": stage, "consumes": consumes, "produces": produces, "dir": Path(dir)}


def test_cli_run_argv_dipole_no_overrides():
    algo = _algo("dipole", ["localfield", "mask", "params"], ["chimap"], "/algos/tkd")
    argv = cli_run_argv(algo, Path("/in"), Path("/out"), AF)
    assert argv == [
        "qsm-ci", "run", "/algos/tkd",
        "--localfield", "/in/localfield.nii.gz",
        "--mask", "/in/mask.nii.gz",
        "--params", "/in/params.json",
        "-o", "/out/chimap.nii.gz", "--runner", "docker",
    ]


def test_cli_run_argv_bfr_and_fieldmapping():
    bfr = _algo("bfr", ["totalfield", "mask", "params"], ["localfield"], "/algos/sharp")
    assert cli_run_argv(bfr, Path("/in"), Path("/out"), AF) == [
        "qsm-ci", "run", "/algos/sharp",
        "--totalfield", "/in/totalfield.nii.gz",
        "--mask", "/in/mask.nii.gz", "--params", "/in/params.json",
        "-o", "/out/localfield.nii.gz", "--runner", "docker",
    ]
    fm = _algo("field-mapping", ["phase", "magnitude", "mask", "params"], ["totalfield"], "/algos/romeo")
    argv = cli_run_argv(fm, Path("/in"), Path("/out"), AF)
    # magnitude IS in consumes; without a real file on disk it is optional-skipped
    assert "--magnitude" not in argv
    assert argv[:5] == ["qsm-ci", "run", "/algos/romeo", "--phase", "/in/phase.nii.gz"]
    assert argv[-4:] == ["-o", "/out/totalfield.nii.gz", "--runner", "docker"]


def test_cli_run_argv_magnitude_optional_present(tmp_path):
    """magnitude in consumes is emitted only when the file exists (the optional-input rule)."""
    algo = _algo("bfr+dipole", ["totalfield", "mask", "params", "magnitude"], ["chimap"], "/algos/medi")
    for fn in ("totalfield.nii.gz", "mask.nii.gz", "params.json"):
        (tmp_path / fn).write_text("x")
    # missing magnitude -> skipped
    argv_missing = cli_run_argv(algo, tmp_path, Path("/out"), AF)
    assert "--magnitude" not in argv_missing
    # present magnitude -> included, in consumes order (last)
    (tmp_path / "magnitude.nii.gz").write_text("x")
    argv_present = cli_run_argv(algo, tmp_path, Path("/out"), AF)
    assert ["--magnitude", str(tmp_path / "magnitude.nii.gz")] == argv_present[-6:-4]


def test_cli_run_argv_overrides_default_str_format():
    """Default value formatting is str(v) — the pipeline / run_algo (tuned pass) behaviour."""
    algo = _algo("bfr", ["totalfield", "mask", "params"], ["localfield"], "/algos/resharp")
    argv = cli_run_argv(algo, Path("/in"), Path("/out"), AF, "apptainer",
                        {"radius": "15", "tik_reg": "0.001"})
    assert "--runner" in argv and argv[argv.index("--runner") + 1] == "apptainer"
    assert ["--set", "radius=15", "--set", "tik_reg=0.001"] == argv[-8:-4]


def test_cli_run_argv_overrides_fmt_callable():
    """sweep.py passes fmt so a swept float 8.0 renders as `8` (its long-standing behaviour)."""
    def fmt(v):
        return f"{v:g}" if isinstance(v, float) else str(v)

    algo = _algo("bfr", ["totalfield", "mask", "params"], ["localfield"], "/algos/resharp")
    argv = cli_run_argv(algo, Path("/in"), Path("/out"), AF, "docker",
                        {"radius": 8.0, "tik_reg": 1e-3, "n": 5}, fmt=fmt)
    sets = [argv[i + 1] for i, a in enumerate(argv) if a == "--set"]
    assert sets == ["radius=8", "tik_reg=0.001", "n=5"]
    # default (str) would instead give 8.0
    argv_str = cli_run_argv(algo, Path("/in"), Path("/out"), AF, "docker", {"radius": 8.0})
    assert "radius=8.0" in argv_str


# ------------------------------------------------------------------ gt_sources


def test_gt_sources_mapping():
    ds = Path("/data/sim/dev")
    src = gt_sources(ds)
    assert src == {
        "phase": ds / "inputs" / "phase.nii.gz",
        "magnitude": ds / "inputs" / "magnitude.nii.gz",
        "mask": ds / "inputs" / "mask.nii.gz",
        "params": ds / "inputs" / "params.json",
        "r2prime": ds / "inputs" / "r2prime.nii.gz",
        "totalfield": ds / "groundtruth" / "totalfield.nii.gz",
        "localfield": ds / "groundtruth" / "localfield.nii.gz",
        "chimap": ds / "groundtruth" / "chimap.nii.gz",
    }


def test_gt_sources_raw_vs_boundary_split():
    """Raw acquisition artifacts come from inputs/; stage boundaries from groundtruth/."""
    src = gt_sources(Path("/d"))
    assert "inputs" in src["phase"].parts and "inputs" in src["mask"].parts
    for boundary in ("totalfield", "localfield", "chimap"):
        assert "groundtruth" in src[boundary].parts


# ------------------------------------------------------------ shard partition


def test_parse_shard():
    assert parse_shard(None) == (None, None)
    assert parse_shard("") == (None, None)
    assert parse_shard("0/1") == (0, 1)
    assert parse_shard("2/5") == (2, 5)


@pytest.mark.parametrize("spec", ["3/3", "5/3", "-1/3"])
def test_parse_shard_out_of_range_raises(spec):
    with pytest.raises(SystemExit):
        parse_shard(spec)


def test_shard_owns():
    assert shard_owns(0, None, None) is True  # sharding off -> owns everything
    assert shard_owns(7, None, None) is True
    assert shard_owns(0, 0, 3) is True
    assert shard_owns(3, 0, 3) is True
    assert shard_owns(1, 0, 3) is False


def test_shard_partition_none_returns_all():
    items = list(range(10))
    assert shard_partition(items, None) == items
    assert shard_partition(items, "") == items
    # returns a copy, not the same list object
    assert shard_partition(items, None) is not items


def test_shard_partition_preserves_order():
    items = ["a", "b", "c", "d", "e", "f", "g"]
    part = shard_partition(items, "0/2")
    assert part == ["a", "c", "e", "g"]  # order preserved, round-robin stride
    assert part == [x for x in items if x in part]


@pytest.mark.parametrize("n", [1, 2, 3, 5, 7, 10, 13])
def test_shard_partition_exact_cover(n):
    """Union of all n shards == the input exactly once each; shards are disjoint."""
    items = list(range(23))
    union = []
    for i in range(n):
        part = shard_partition(items, f"{i}/{n}")
        assert part == sorted(part)  # order preserved (ints ascending here)
        union += part
    assert sorted(union) == items
    assert len(union) == len(items)  # no item counted twice


def test_shard_partition_n_greater_than_len():
    items = [10, 20, 30]
    # 5 shards over 3 items: shards 0..2 get one each, 3 and 4 get nothing
    parts = [shard_partition(items, f"{i}/5") for i in range(5)]
    assert parts == [[10], [20], [30], [], []]
    assert sorted(x for p in parts for x in p) == items


def test_shard_partition_one_of_one():
    items = list(range(6))
    assert shard_partition(items, "0/1") == items


# --------------------------------------------------------------------- eval_argv


def test_eval_argv_pipeline_chi_with_runtime_and_seg():
    argv = eval_argv("py", Path("/eval.py"), Path("/r.nii.gz"), Path("/gt/chimap.nii.gz"), "chi",
                     Path("/m.nii.gz"), "chimap", Path("/o.json"),
                     stage="bfr+dipole", name="medi", track="sim",
                     runtime=12.5, seg=Path("/gt/dseg.nii.gz"))
    assert argv == [
        "py", "/eval.py", "--recon", "/r.nii.gz", "--truth", "/gt/chimap.nii.gz",
        "--kind", "chi", "--mask", "/m.nii.gz", "--artifact", "chimap", "--out", "/o.json",
        "--stage", "bfr+dipole", "--name", "medi", "--track", "sim",
        "--runtime", "12.5", "--seg", "/gt/dseg.nii.gz",
    ]


def test_eval_argv_no_runtime_no_seg():
    argv = eval_argv("py", Path("/e.py"), Path("/r"), Path("/t"), "field", Path("/m"),
                     "localfield", Path("/o"), stage="sweep", name="sweep", track="sim")
    assert "--runtime" not in argv and "--seg" not in argv
    assert argv[-3:] == ["--name", "sweep", "--track"] or argv[-1] == "sim"
    assert argv[-6:] == ["--stage", "sweep", "--name", "sweep", "--track", "sim"]


def test_eval_argv_seg_without_runtime():
    """sweep/combo pass seg but never runtime — seg must still land at the tail in the right order."""
    argv = eval_argv("py", Path("/e.py"), Path("/r"), Path("/t"), "chi", Path("/m"),
                     "chimap", Path("/o"), stage="combo-sweep", name="combo-sweep", track="sim",
                     seg=Path("/gt/dseg.nii.gz"))
    assert "--runtime" not in argv
    assert argv[-2:] == ["--seg", "/gt/dseg.nii.gz"]


def test_eval_argv_runtime_int_stringified():
    argv = eval_argv("py", Path("/e.py"), Path("/r"), Path("/t"), "chi", Path("/m"),
                     "chimap", Path("/o"), stage="dipole", name="tv", track="sim", runtime=3)
    assert argv[argv.index("--runtime") + 1] == "3"
