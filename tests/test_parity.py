"""scripts/parity.py — the comparison, threshold and pair logic of the parity workflow.

Tiny synthetic arrays only: no containers, no dataset. The container runs themselves go through
`qsm-ci run` (tested elsewhere); here we check what is measured and when the job fails.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import nibabel as nib
import numpy as np
import pytest
import yaml

import parity

ROOT = Path(__file__).resolve().parent.parent


def _mask(shape=(6, 6, 6)):
    m = np.zeros(shape, np.uint8)
    m[1:5, 1:5, 1:5] = 1
    return m


# --- compare_maps -------------------------------------------------------------------------------

def test_identical_maps_agree_exactly():
    rng = np.random.default_rng(0)
    a = rng.normal(size=(6, 6, 6))
    m = parity.compare_maps(a, a.copy(), _mask())
    assert m["kind"] == "continuous"
    assert m["nrmse"] == 0 and m["max_abs"] == 0 and m["p99_abs"] == 0
    assert m["correlation"] == pytest.approx(1.0)


def test_continuous_metrics_inside_mask_only():
    rng = np.random.default_rng(1)
    ref = rng.normal(size=(6, 6, 6))
    cand = ref + 0.1
    cand[0, 0, 0] = 1e6                          # outside the mask: must not count
    m = parity.compare_maps(ref, cand, _mask())
    inside = ref[_mask() > 0]
    assert m["nrmse"] == pytest.approx(100 * 0.1 * math.sqrt(inside.size) / np.linalg.norm(inside))
    assert m["max_abs"] == pytest.approx(0.1)
    assert m["p99_abs"] == pytest.approx(0.1)
    assert m["correlation"] == pytest.approx(1.0)
    assert m["voxels"] == 64


def test_scaled_candidate_keeps_correlation_but_not_nrmse():
    rng = np.random.default_rng(2)
    ref = rng.normal(size=(6, 6, 6))
    m = parity.compare_maps(ref, 2 * ref, _mask())
    assert m["correlation"] == pytest.approx(1.0)
    assert m["nrmse"] == pytest.approx(100.0)


def test_binary_maps_use_dice():
    ref = np.zeros((6, 6, 6)); ref[1:3, 1:5, 1:5] = 1     # 32 voxels
    cand = np.zeros((6, 6, 6)); cand[2:4, 1:5, 1:5] = 1   # 32 voxels, 16 shared
    m = parity.compare_maps(ref, cand, _mask())
    assert m == {"kind": "binary", "dice": pytest.approx(0.5), "n_ref": 32, "n_cand": 32,
                 "voxels": 64}


def test_empty_binary_maps_agree():
    z = np.zeros((6, 6, 6))
    assert parity.compare_maps(z, z, _mask())["dice"] == 1.0


def test_nonfinite_voxels_are_counted_and_fail():
    ref = np.ones((6, 6, 6)) + np.arange(216).reshape(6, 6, 6) * 1e-3
    cand = ref.copy(); cand[2, 2, 2] = np.nan
    m = parity.compare_maps(ref, cand, _mask())
    assert m["nonfinite"] == 1 and m["nrmse"] == 0
    rows = parity.check(m, {"nrmse_max": 1})
    assert [r["metric"] for r in rows if not r["ok"]] == ["nonfinite"]


def test_shape_mismatch_is_an_error():
    with pytest.raises(ValueError, match="shape mismatch"):
        parity.compare_maps(np.zeros((6, 6, 6)), np.zeros((6, 6, 5)), _mask())


# --- check / evaluate ---------------------------------------------------------------------------

def test_check_directions_and_bounds_inclusive():
    m = {"nrmse": 5.0, "correlation": 0.9}
    rows = {r["metric"]: r["ok"] for r in parity.check(m, {"nrmse_max": 5.0, "correlation_min": 0.9})}
    assert rows == {"nrmse": True, "correlation": True}
    rows = {r["metric"]: r["ok"] for r in parity.check(m, {"nrmse_max": 4.9, "correlation_min": 0.91})}
    assert rows == {"nrmse": False, "correlation": False}


def test_check_missing_or_nan_metric_fails():
    rows = parity.check({"correlation": float("nan")}, {"correlation_min": 0.5, "dice_min": 0.5})
    assert not any(r["ok"] for r in rows)


def test_check_rejects_unknown_limit_key():
    with pytest.raises(ValueError, match="unknown limit"):
        parity.check({"nrmse": 1}, {"nrmse": 2})


def test_evaluate_final_without_limits_fails():
    v = parity.evaluate({"chimap": {"kind": "continuous", "nrmse": 1.0}}, {}, "chimap")
    assert not v["ok"] and v["maps"]["chimap"]["status"] == "fail"


def test_evaluate_intermediate_without_limits_is_info():
    res = {"chimap": {"kind": "continuous", "nrmse": 1.0},
           "vessel_mask": {"kind": "binary", "dice": 0.2}}
    v = parity.evaluate(res, {"chimap": {"nrmse_max": 2}}, "chimap")
    assert v["ok"]
    assert v["maps"]["vessel_mask"]["status"] == "info"


def test_evaluate_intermediate_limit_exceeded_fails():
    res = {"chimap": {"kind": "continuous", "nrmse": 1.0},
           "vessel_mask": {"kind": "binary", "dice": 0.2}}
    cfg = {"chimap": {"nrmse_max": 2}, "intermediates": {"vessel_mask": {"dice_min": 0.9}}}
    v = parity.evaluate(res, cfg, "chimap")
    assert not v["ok"] and v["maps"]["vessel_mask"]["status"] == "fail"


# --- derive_limits ------------------------------------------------------------------------------

def test_derived_limits_pass_the_measurement_they_came_from():
    m = {"kind": "continuous", "nrmse": 12.3456, "correlation": 0.912345, "max_abs": 0.4321,
         "p99_abs": 0.0123}
    lim = parity.derive_limits(m)
    assert lim["nrmse_max"] >= 12.3456 * 1.1 + 0.5
    assert lim["correlation_min"] <= 0.912345 - 0.01
    assert lim["max_abs_max"] >= 0.4321 * 1.25
    assert all(r["ok"] for r in parity.check(m, lim))


def test_derived_limits_binary():
    lim = parity.derive_limits({"kind": "binary", "dice": 0.98765})
    assert lim == {"dice_min": pytest.approx(0.977)}


def test_derived_limits_perfect_agreement():
    m = {"kind": "continuous", "nrmse": 0.0, "correlation": 1.0, "max_abs": 0.0, "p99_abs": 0.0}
    lim = parity.derive_limits(m)
    assert lim["nrmse_max"] == pytest.approx(0.5)
    assert lim["max_abs_max"] == lim["p99_abs_max"] == 1e-6   # float noise is not a regression
    assert all(r["ok"] for r in parity.check(m, lim))


# --- pairs / matrix -----------------------------------------------------------------------------

def test_discover_pairs_needs_an_original_and_a_port(tmp_path):
    for slug, alg, src in (("x-orig", "x", "vendor"), ("x-jl", "x", "qsmjl"), ("x-qsmrs", "x", "qsmrs"),
                           ("y-a-qsmrs", "y", "qsmrs"), ("y-b-qsmrs", "y", "qsmrs"),
                           ("z-orig", "z", "vendor")):
        (tmp_path / slug).mkdir()
        (tmp_path / slug / "algorithm.yml").write_text(
            yaml.safe_dump({"algorithm": alg, "source": src, "stage": "dipole"}))
    assert parity.discover_pairs(tmp_path) == {
        "x": {"original": ["x-jl", "x-orig"], "port": ["x-qsmrs"]}}


def test_real_thresholds_enabled_pairs_track_their_qsmrs_sources():
    """Staleness rule (b) needs each enabled pair's QSM.rs paths; a gap names what blocks it."""
    for name, cfg in parity.load_thresholds().items():
        if cfg.get("enabled"):
            assert cfg.get("qsmrs_paths"), f"{name}: enabled without qsmrs_paths"
            assert all(p.startswith("src/") for p in cfg["qsmrs_paths"]), name
            assert not cfg.get("blocked_by"), f"{name}: enabled but blocked_by"


ARTIFACTS = ("chimap", "localfield", "totalfield", "chi-para", "chi-dia", "mask")


def test_real_thresholds_name_real_pairs():
    """Every enabled pair matches algorithm.yml: an original and a QSM.rs port of one algorithm.
    (A disabled pair may name an original that is still on its way, e.g. a Julia one.)"""
    th, manifests = parity.load_thresholds(), parity._manifests()
    assert th.get("qsmart", {}).get("enabled"), "the QSMART pair is enabled"
    datasets = json.loads((ROOT / "scripts" / "datasets.json").read_text())
    for name, cfg in th.items():
        if cfg.get("enabled"):
            assert parity.pair_problems(name, cfg, manifests) == [], name
        for ds, dcfg in (cfg.get("datasets") or {}).items():
            assert ds in datasets, ds
            for side in ("reference", "candidate"):
                for slug in (dcfg or {}).get(f"{side}_prefix") or []:
                    assert (ROOT / "algorithms" / slug / "algorithm.yml").exists(), slug
            final = [a for a in ARTIFACTS if a in (dcfg or {})]   # the final map's limits
            for a in final:
                parity.check({}, dcfg[a])                         # well-formed limit keys
            for lim in ((dcfg or {}).get("intermediates") or {}).values():
                parity.check({}, lim)
            if cfg.get("enabled"):
                assert final, f"{name}/{ds}: an enabled pair needs limits"


def test_pair_problems():
    m = {"a-orig": {"algorithm": "a", "source": "vendor"}, "a-jl": {"algorithm": "a", "source": "qsmjl"},
         "a-qsmrs": {"algorithm": "a", "source": "qsmrs"}, "b-qsmrs": {"algorithm": "b", "source": "qsmrs"}}
    # either original of an algorithm with two can be the declared reference
    assert parity.pair_problems("a", {"reference": "a-orig", "candidate": "a-qsmrs"}, m) == []
    assert parity.pair_problems("a-jl", {"reference": "a-jl", "candidate": "a-qsmrs"}, m) == []
    assert any("share" in p for p in
               parity.pair_problems("x", {"reference": "a-orig", "candidate": "b-qsmrs"}, m))
    assert any("not a QSM.rs port" in p for p in
               parity.pair_problems("x", {"reference": "a-orig", "candidate": "a-jl"}, m))
    assert any("is a QSM.rs port" in p for p in
               parity.pair_problems("x", {"reference": "b-qsmrs", "candidate": "a-qsmrs"}, m))
    assert any("no algorithms/gone" in p for p in
               parity.pair_problems("x", {"reference": "gone", "candidate": "a-qsmrs"}, m))
    rows = parity.pair_listing({"a": {"original": ["a-jl", "a-orig"], "port": ["a-qsmrs"]},
                                "c": {"original": ["c-o"], "port": ["c-qsmrs"]}},
                               {"a": {"reference": "a-orig", "candidate": "a-qsmrs", "enabled": True}}, m)
    assert [(r["pair"], r["algorithm"]) for r in rows] == [("a", "a"), (None, "c")]


def test_apply_names_renames_and_complements(tmp_path):
    inter = tmp_path / "i"
    mask = np.zeros((4, 4, 4)); mask[1:3, 1:3, 1:3] = 1
    tissue = mask.copy(); tissue[1, 1, 1] = 0             # one vessel voxel
    _save(tmp_path / "mask.nii.gz", mask)
    _save(inter / "tfs.nii.gz", np.ones((4, 4, 4)))
    _save(inter / "vasc_only.nii.gz", tissue)
    parity.apply_names(inter, {"tfs": "totalfield", "vasc_only": {"name": "vessel_mask",
                                                                 "complement": True},
                               "absent": "whatever"}, tmp_path / "mask.nii.gz")
    assert sorted(p.name for p in inter.iterdir()) == ["totalfield.nii.gz", "vessel_mask.nii.gz"]
    vm = parity._load(inter / "vessel_mask.nii.gz")
    assert vm.sum() == 1 and vm[1, 1, 1] == 1


def _pm(th, alg, ds):
    """plan_matrix without the repo checks, reduced to (pair, dataset)."""
    return [(j["algorithm"], j["phantom"]) for j in parity.plan_matrix(th, alg, ds, manifests={},
                                                                         datasets={})]


def test_plan_matrix():
    th = {"a": {"enabled": True, "datasets": {"sim": {}, "kki": {}}},
          "b": {"enabled": False, "datasets": {"sim": {}}},
          "c": {"enabled": False}}
    assert _pm(th, "enabled", "configured") == [("a", "kki"), ("a", "sim")]
    assert _pm(th, "b", "sim") == [("b", "sim")]
    assert _pm(th, "a", "other") == [("a", "other")]
    with pytest.raises(SystemExit):
        _pm(th, "nope", "sim")


def test_select_pairs_takes_lists_and_selectors():
    th = {"a": {"enabled": True, "datasets": {"sim": {}}}, "b": {"datasets": {"sim": {}}},
          "c": {"enabled": False}}
    assert parity.select_pairs(th, "b,a") == ["a", "b"]           # thresholds.yml order
    assert parity.select_pairs(th, " a , a ") == ["a"]            # no duplicates
    assert parity.select_pairs(th, "all-configured") == ["a", "b"]
    assert parity.select_pairs(th, "enabled,c") == ["a", "c"]
    for bad in ("a,nope", "", "qsmart,,x"):
        with pytest.raises(SystemExit):
            parity.select_pairs(th, bad)


def test_plan_matrix_validates_before_anything_runs():
    th = {"a": {"reference": "a-orig", "candidate": "a-qsmrs", "datasets": {"sim": {}}},
          "b": {"reference": "b-orig", "candidate": "a-qsmrs", "datasets": {"sim": {}}}}
    m = {"a-orig": {"algorithm": "a", "source": "x"}, "a-qsmrs": {"algorithm": "a", "source": "qsmrs"},
         "b-orig": {"algorithm": "b", "source": "x"}}
    with pytest.raises(SystemExit, match="shares one algorithm"):
        parity.plan_matrix(th, "a,b", "configured", manifests=m, datasets={"sim": {}})
    with pytest.raises(SystemExit, match="not in scripts/datasets.json"):
        parity.plan_matrix(th, "a", "kki", manifests=m, datasets={"sim": {}})


def test_real_matrix_routes_runners():
    """Every configured pair whose sides are here plans, with a runner and a cap for each job."""
    th, m = parity.load_thresholds(), parity._manifests()
    here = [a for a, c in th.items() if c.get("datasets") and not parity.pair_problems(a, c, m)]
    jobs = parity.plan_matrix(th, ",".join(here), "configured")
    assert jobs and all(j["runs_on"] and j["timeout"] > 0 for j in jobs)


def test_plan_matrix_flags_pairs_that_need_the_weights():
    """A pair with `qsmrs_models` asks the workflow to add the ONNX weights to a qsmxt build."""
    th = {"a": {"qsmrs_models": True, "datasets": {"sim": {}}}, "b": {"datasets": {"sim": {}}}}
    jobs = parity.plan_matrix(th, "a,b", "configured", manifests={}, datasets={})
    assert {j["algorithm"]: j["models"] for j in jobs} == {"a": True, "b": False}


def test_side_set_dataset_wins():
    cfg = {"reference_set": {"pad": -1, "a": 1}, "datasets": {"kki": {"reference_set": {"a": 2}}}}
    assert parity.side_set(cfg, "reference", "kki") == {"pad": -1, "a": 2}
    assert parity.side_set(cfg, "reference", "sim") == {"pad": -1, "a": 1}
    assert parity.side_set(cfg, "candidate", "sim") == {}


def test_side_chain_prefix():
    cfg = {"reference": "r", "candidate": "c",
           "datasets": {"kki": {"candidate_prefix": ["fm"]}}}
    assert parity.side_chain(cfg, "candidate", "kki") == ["fm", "c"]
    assert parity.side_chain(cfg, "reference", "kki") == ["r"]
    assert parity.side_chain(cfg, "candidate", "sim") == ["c"]


# --- compare end to end on NIfTI dirs -----------------------------------------------------------

def _save(path: Path, arr):
    path.parent.mkdir(parents=True, exist_ok=True)
    nib.save(nib.Nifti1Image(np.asarray(arr, np.float32), np.eye(4)), str(path))


def _work(tmp_path, cand_shift=0.0, inter=True):
    rng = np.random.default_rng(3)
    chi = rng.normal(size=(6, 6, 6))
    vm = np.zeros((6, 6, 6)); vm[2:4, 2:4, 2:4] = 1
    ds = tmp_path / "ds"
    _save(ds / "inputs" / "mask.nii.gz", _mask())
    for side, shift in (("reference", 0.0), ("candidate", cand_shift)):
        d = tmp_path / "work" / side
        _save(d / "chimap.nii.gz", chi + shift)
        (d / "provenance.json").parent.mkdir(parents=True, exist_ok=True)
        (d / "provenance.json").write_text(json.dumps({"chain": [side], "final": "chimap"}))
        if inter:
            _save(d / "intermediates" / "vessel_mask.nii.gz", vm)
    _save(tmp_path / "work" / "reference" / "intermediates" / "reliability.nii.gz", _mask())
    return ds, tmp_path / "work"


def _thresholds(tmp_path, limits):
    t = tmp_path / "t.yml"
    t.write_text(yaml.safe_dump({"pairs": {"p": {"reference": "r", "candidate": "c", "enabled": True,
                                                 "datasets": {"sim": limits}}}}))
    return t


def _compare(tmp_path, ds, work, t, *extra):
    rep, js = tmp_path / "r.md", tmp_path / "r.json"
    rc = parity.main(["--thresholds", str(t), "compare", "--algorithm", "p", "--phantom", "sim",
                      "--dataset", str(ds), "--work", str(work), "--report", str(rep),
                      "--json", str(js), *extra])
    return rc, rep.read_text(), json.loads(js.read_text())


def test_compare_passes_and_joins_intermediates_by_name(tmp_path):
    ds, work = _work(tmp_path, cand_shift=0.01)
    t = _thresholds(tmp_path, {"chimap": {"max_abs_max": 0.02},
                               "intermediates": {"vessel_mask": {"dice_min": 0.99}}})
    rc, rep, js = _compare(tmp_path, ds, work, t)
    assert rc == 0 and js["ok"]
    assert set(js["maps"]) == {"chimap", "vessel_mask"}
    assert js["unmatched"] == {"reference": ["reliability"], "candidate": []}
    assert "Parity holds" in rep and "`reliability`" in rep


def test_compare_fails_on_regression(tmp_path):
    ds, work = _work(tmp_path, cand_shift=0.05)
    t = _thresholds(tmp_path, {"chimap": {"max_abs_max": 0.02}})
    rc, rep, js = _compare(tmp_path, ds, work, t)
    assert rc == 1 and not js["ok"] and "Parity regression" in rep


def test_compare_baseline_never_fails_and_suggests_limits(tmp_path):
    ds, work = _work(tmp_path, cand_shift=0.05)
    t = _thresholds(tmp_path, {})
    rc, rep, js = _compare(tmp_path, ds, work, t, "--baseline")
    assert rc == 0 and "❌" not in rep   # a measurement, not a verdict
    block = rep.split("```yaml\n", 1)[1].split("```", 1)[0]
    sugg = yaml.safe_load(block)["datasets"]["sim"]
    assert "nrmse_max" in sugg["chimap"]
    assert sugg["intermediates"]["vessel_mask"] == {"dice_min": 0.99}
    # pasting the suggestion back makes the same data pass
    t2 = _thresholds(tmp_path, sugg)
    rc, _, js = _compare(tmp_path, ds, work, t2)
    assert rc == 0 and js["ok"]


# --- `qsm-ci run --intermediates` (the hand-off parity relies on) --------------------------------

def _inter_method(tmp_path) -> Path:
    d = tmp_path / "inter-bfr"
    d.mkdir()
    (d / "algorithm.yml").write_text("name: Inter BFR\nslug: inter-bfr\nstage: bfr\nimage: bash:latest\n"
                                     "run: bash run.sh\n")
    (d / "run.sh").write_text(
        'set -euo pipefail\nIN="$1"; OUT="$2"\ncp "$IN/totalfield.nii.gz" "$OUT/localfield.nii.gz"\n'
        'if [ -n "${QSMCI_INTERMEDIATES:-}" ]; then\n'
        '  cp "$IN/mask.nii.gz" "$QSMCI_INTERMEDIATES/vessel_mask.nii.gz"\nfi\n')
    return d


def _bfr_inputs(tmp_path):
    _save(tmp_path / "tf.nii.gz", np.ones((4, 4, 4)))
    _save(tmp_path / "mask.nii.gz", np.ones((4, 4, 4)))
    return ["--runner", "local", "--totalfield", str(tmp_path / "tf.nii.gz"),
            "--mask", str(tmp_path / "mask.nii.gz"), "-o", str(tmp_path / "out.nii.gz")]


def test_cli_collects_intermediates(tmp_path):
    from qsm_ci import runner
    m = _inter_method(tmp_path)
    msgs = []
    rc = runner.run_command([str(m), *_bfr_inputs(tmp_path), "--intermediates",
                             str(tmp_path / "inter")], log=msgs.append)
    assert rc == 0
    assert (tmp_path / "inter" / "vessel_mask.nii.gz").exists()
    assert any("vessel_mask" in s for s in msgs)


def test_cli_without_intermediates_flag_sets_nothing(tmp_path):
    from qsm_ci import runner
    m = _inter_method(tmp_path)
    assert runner.run_command([str(m), *_bfr_inputs(tmp_path)], log=lambda *_: None) == 0
    assert not (tmp_path / "inter").exists()


def test_cli_image_override_needs_a_container_runner(tmp_path):
    from qsm_ci import runner
    m = _inter_method(tmp_path)
    with pytest.raises(SystemExit, match="container runner"):
        runner.run_command([str(m), *_bfr_inputs(tmp_path), "--image", "x:y"], log=lambda *_: None)


def test_cli_image_override_replaces_the_pinned_image(tmp_path, monkeypatch):
    from qsm_ci import runner
    seen = {}

    def fake_run(algo, idir, odir, rn, log, timeout=None, intermediates=False):
        seen.update(algo)
        odir.mkdir(parents=True, exist_ok=True)
        import shutil
        shutil.copy(idir / "totalfield.nii.gz", odir / "localfield.nii.gz")
        return 0.0

    monkeypatch.setattr(runner, "_run_container", fake_run)
    monkeypatch.setattr(runner, "check_runner", lambda *a, **k: True)
    m = _inter_method(tmp_path)
    args = [a if a != "local" else "docker" for a in _bfr_inputs(tmp_path)]
    assert runner.run_command([str(m), *args, "--image", "qsmxt-under-test:1"],
                              log=lambda *_: None) == 0
    assert seen["image"] == "qsmxt-under-test:1" and seen["image_local_first"]


def test_run_side_puts_only_qsmrs_steps_in_the_image_under_test(tmp_path, monkeypatch):
    """The override must reach every QSM.rs step and no other (discovery drops `source:`)."""
    import subprocess as sp
    calls = []

    def fake(argv, env=None, check=False, **kw):
        if argv[:2] == ["qsm-ci", "run"]:
            calls.append(argv)
            out = Path(argv[argv.index("-o") + 1])
            out.parent.mkdir(parents=True, exist_ok=True)
            _save(out, np.zeros((4, 4, 4)))
        return sp.CompletedProcess(argv, 1, "", "")

    monkeypatch.setattr(parity.subprocess, "run", fake)
    ds = tmp_path / "ds"
    _save(ds / "inputs" / "mask.nii.gz", np.ones((4, 4, 4)))
    _save(ds / "inputs" / "phase.nii.gz", np.zeros((4, 4, 4, 2)))
    _save(ds / "inputs" / "magnitude.nii.gz", np.ones((4, 4, 4, 2)))
    (ds / "inputs" / "params.json").write_text(json.dumps(
        {"TE": [0.004, 0.008], "B0": 3, "B0_dir": [0, 0, 1], "voxel_size": [1, 1, 1]}))
    prov = parity.run_side(["laplacian-qsmrs", "qsmart-qsmrs"], ds, tmp_path / "w", "docker",
                           qsmrs_image="under-test:1", log=lambda *_: None)
    assert all(a[a.index("--image") + 1] == "under-test:1" for a in calls) and len(calls) == 2
    assert [s["image"] for s in prov["steps"]] == ["under-test:1", "under-test:1"]
    assert (tmp_path / "w" / "intermediates" / "totalfield.nii.gz").exists()   # the prefix's output
    calls.clear()
    parity.run_side(["qsmart-matlab"], ds, tmp_path / "w2", "docker", qsmrs_image="under-test:1",
                    log=lambda *_: None)
    assert "--image" not in calls[0]


def _fake_qsmci(calls):
    import subprocess as sp

    def fake(argv, env=None, check=False, **kw):
        if argv[:2] == ["qsm-ci", "run"]:
            calls.append(argv)
            out = Path(argv[argv.index("-o") + 1])
            out.parent.mkdir(parents=True, exist_ok=True)
            _save(out, np.zeros((4, 4, 4)))
        return sp.CompletedProcess(argv, 1, "", "")
    return fake


def _dipole_ds(tmp_path):
    ds = tmp_path / "ds"
    _save(ds / "inputs" / "mask.nii.gz", np.ones((4, 4, 4)))
    _save(ds / "groundtruth" / "localfield.nii.gz", np.zeros((4, 4, 4)))
    (ds / "inputs" / "params.json").write_text(json.dumps(
        {"TE": [0.004], "B0": 3, "B0_dir": [0, 0, 1], "voxel_size": [1, 1, 1]}))
    return ds


def test_run_side_sets_only_the_pairs_own_method(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(parity.subprocess, "run", _fake_qsmci(calls))
    ds = _dipole_ds(tmp_path)
    _save(ds / "groundtruth" / "totalfield.nii.gz", np.zeros((4, 4, 4)))
    prov = parity.run_side(["vsharp-qsmrs", "tkd-qsmrs"], ds, tmp_path / "w", "docker",
                           overrides={"threshold": 0.2}, log=lambda *_: None)
    assert "--set" not in calls[0]
    assert calls[1][calls[1].index("--set") + 1] == "threshold=0.2"
    assert prov["steps"][1]["set"] == {"threshold": 0.2} and "set" not in prov["steps"][0]


def _qsmart_ds(tmp_path):
    ds = tmp_path / "ds"
    _save(ds / "inputs" / "mask.nii.gz", np.ones((4, 4, 4)))
    _save(ds / "inputs" / "phase.nii.gz", np.zeros((4, 4, 4, 2)))
    _save(ds / "inputs" / "magnitude.nii.gz", np.ones((4, 4, 4, 2)))
    _save(ds / "groundtruth" / "totalfield.nii.gz", np.zeros((4, 4, 4)))
    (ds / "inputs" / "params.json").write_text(json.dumps(
        {"TE": [0.004, 0.008], "B0": 3, "B0_dir": [0, 0, 1], "voxel_size": [1, 1, 1]}))
    return ds


def test_qsmart_pair_feeds_the_originals_reliability(tmp_path, monkeypatch):
    """`feed: {reliability: reliability}`: the original's own R_0 (written as `R_0`, compared as
    `reliability`) reaches qsmart-qsmrs as `--reliability`, next to the fed total field."""
    import argparse
    import subprocess as sp
    calls = []
    r0 = np.zeros((4, 4, 4))
    r0[1:3, 1:3, 1:3] = 1

    def fake(argv, env=None, check=False, **kw):
        if argv[:2] == ["qsm-ci", "run"]:
            calls.append(argv)
            out = Path(argv[argv.index("-o") + 1])
            _save(out, np.zeros((4, 4, 4)))
            if argv[2].endswith("qsmart-matlab"):
                inter = Path(argv[argv.index("--intermediates") + 1])
                _save(inter / "tfs.nii.gz", np.full((4, 4, 4), 0.5))
                _save(inter / "R_0.nii.gz", r0)
        return sp.CompletedProcess(argv, 1, "", "")

    monkeypatch.setattr(parity.subprocess, "run", fake)
    for ds_key in ("sim", "s002001-kki-achieva-bridge-run1"):
        calls.clear()
        work = tmp_path / ds_key
        args = argparse.Namespace(thresholds=parity.THRESHOLDS, algorithm="qsmart", phantom=ds_key,
                                  dataset=str(_qsmart_ds(tmp_path / ds_key)), work=str(work),
                                  runner="docker", qsmrs_image="")
        assert parity.cmd_run(args) == 0
        cand = calls[-1]
        assert cand[2].endswith("qsmart-qsmrs")
        rel = Path(cand[cand.index("--reliability") + 1])
        assert rel.name == "reliability.nii.gz"
        assert np.array_equal(nib.load(str(rel)).get_fdata(), r0)
        tf = Path(cand[cand.index("--totalfield") + 1])
        assert np.allclose(nib.load(str(tf)).get_fdata(), 0.5)   # the original's, not the dataset's
        prov = json.loads((work / "candidate" / "provenance.json").read_text())
        assert prov["steps"][0]["fed"] == ["reliability", "totalfield"]


def test_reliability_is_mounted_only_when_fed(tmp_path, monkeypatch):
    """Scoring and an unfed parity side never pass R_0: no dataset ships it, and it is optional."""
    import pipeline
    from scoring import cli_run_argv, gt_sources
    from qsm_ci.stages import ARTIFACT_FILE
    ds = _qsmart_ds(tmp_path)
    algo = parity._algo("qsmart-qsmrs")
    assert "reliability" in algo["consumes"] and "reliability" in algo["optional"]
    idir = tmp_path / "in"
    pipeline.prepare_input(algo["consumes"], gt_sources(ds), idir, algo["optional"])
    assert not (idir / "reliability.nii.gz").exists()
    assert "--reliability" not in cli_run_argv(algo, idir, tmp_path / "out", ARTIFACT_FILE)
    calls = []
    monkeypatch.setattr(parity.subprocess, "run", _fake_qsmci(calls))
    parity.run_side(["qsmart-qsmrs"], ds, tmp_path / "w", "docker", log=lambda *_: None)
    assert "--reliability" not in calls[0]


@pytest.mark.parametrize("fed", [False, True])
def test_qsmart_qsmrs_run_sh_passes_reliability_when_present(tmp_path, fed):
    """run.sh hands `qsmxt qsmart --reliability` the mounted R_0, and nothing without one."""
    import os
    import shutil
    import subprocess as sp
    if not shutil.which("jq"):
        pytest.skip("run.sh needs jq")
    inp, out, bin_ = tmp_path / "in", tmp_path / "out", tmp_path / "bin"
    for d in (inp, out, bin_):
        d.mkdir()
    (inp / "params.json").write_text(json.dumps({"TE": [0.004], "B0": 3, "B0_dir": [0, 0, 1]}))
    if fed:
        (inp / "reliability.nii.gz").write_bytes(b"r0")
    log = tmp_path / "argv"
    stub = bin_ / "qsmxt"
    stub.write_text(f'#!/bin/sh\n[ "$2" = --help ] && exit 0\nprintf "%s\\n" "$@" > {log}\n')
    stub.chmod(0o755)
    env = {**os.environ, "PATH": f"{bin_}:{os.environ['PATH']}"}
    env.pop("QSMCI_INTERMEDIATES", None)
    sp.run(["bash", str(ROOT / "algorithms" / "qsmart-qsmrs" / "run.sh"), str(inp), str(out)],
           env=env, check=True)
    argv = log.read_text().split("\n")
    if fed:
        assert argv[argv.index("--reliability") + 1] == str(inp / "reliability.nii.gz")
    else:
        assert "--reliability" not in argv


def test_ci_skip_port_runs_only_against_a_qsmxt_build(tmp_path, monkeypatch):
    """A ci_skip port (its pinned qsmxt lacks it) runs in parity once a build is supplied; scoring
    discovery still skips it."""
    import pipeline
    real = parity._manifests()
    fake = {**real, "tkd-qsmrs": {**real["tkd-qsmrs"], "ci_skip": True}}
    monkeypatch.setattr(parity, "_manifests", lambda *a, **k: fake)
    orig = pipeline.discover_algorithms
    monkeypatch.setattr(pipeline, "discover_algorithms",
                        lambda *a, include=None, **k: [x for x in orig(*a, include=include, **k)
                                                       if x["slug"] != "tkd-qsmrs"
                                                       or "tkd-qsmrs" in (include or ())])
    with pytest.raises(SystemExit, match="ci_skip"):
        parity._algo("tkd-qsmrs")
    assert parity._algo("tkd-qsmrs", "qsmxt-under-test:1")["slug"] == "tkd-qsmrs"


def test_discovery_skips_parity_only_unless_included(tmp_path, monkeypatch):
    import pipeline
    for slug, extra in (("m-orig", "parity_only: true\n"), ("m-port", "")):
        d = tmp_path / slug
        d.mkdir()
        (d / "algorithm.yml").write_text(f"name: {slug}\nstage: dipole\nimage: x:y\n{extra}")
    monkeypatch.setenv("QSMCI_ALGORITHMS_DIR", str(tmp_path))
    assert [a["slug"] for a in pipeline.discover_algorithms()] == ["m-port"]
    assert [a["slug"] for a in pipeline.discover_algorithms(include={"m-orig"})] == ["m-orig", "m-port"]


def test_parse_qsmrs_version():
    out = ("qsmxt 10.0.0\nQSM.rs (qsm-core): v0.39.0 (42ab620190ad315c9dcf7aa8ec4a036402002b7e)\n"
           "deep-learning models: enabled\n")
    assert parity.parse_qsmrs_version(out) == {"qsmrs_version": "0.39.0",
                                               "qsmrs_commit": "42ab620190ad315c9dcf7aa8ec4a036402002b7e"}
    assert parity.parse_qsmrs_version("qsmxt 9\n") == {}
    assert parity.parse_qsmrs_version("qsmxt 0.0.0\nQSM.rs (qsm-core): rev-da928e0c5bfc7670dc44efe842623f5fe4a591c0\n") \
        == {"qsmrs_version": None, "qsmrs_commit": "da928e0c5bfc7670dc44efe842623f5fe4a591c0"}


# --- run history and staleness ---------------------------------------------------------------------

REF_IMG = "ghcr.io/x/orig@sha256:" + "a" * 64
CFG = {"reference": "p-orig", "candidate": "p-qsmrs", "enabled": True,
       "qsmrs_paths": ["src/inversion/p.rs", "src/kernels"],
       "datasets": {"sim": {"chimap": {"nrmse_max": 2.0}, "measured": {"x": "run 1"}}}}
MANIFESTS = {"p-orig": {"image": REF_IMG, "algorithm": "p"},
             "p-qsmrs": {"image": "ghcr.io/x/qsmxt@sha256:" + "b" * 64, "algorithm": "p",
                         "source": "qsmrs"}}


def _parity_json(ok=True, nrmse=1.0):
    return {"algorithm": "p", "phantom": "sim", "baseline": False, "ok": ok,
            "maps": {"chimap": {"metrics": {"kind": "continuous", "nrmse": nrmse, "correlation": 0.99,
                                            "max_abs": 0.1, "p99_abs": 0.01, "nonfinite": 0},
                                "status": "pass" if ok else "fail", "limits": {"nrmse_max": 2.0},
                                "checks": [{"metric": "nrmse", "value": nrmse, "op": "<=",
                                            "limit": 2.0, "ok": ok}]}},
            "provenance": {"reference": {"steps": [{"slug": "p-orig", "image": REF_IMG, "id": "sha256:r"}]},
                           "candidate": {"steps": [{"slug": "p-qsmrs", "image": "qsmxt-under-test:9",
                                                    "id": "sha256:c", "qsmxt": "qsmxt 10.1.0",
                                                    "qsmrs_version": "0.40.0",
                                                    "qsmrs_commit": "c" * 40}]}}}


RUN = {"date": "2026-10-28T00:00:00Z", "run_id": "1", "run_url": "https://x/1", "qsmci_commit": "q",
       "qsmrs_ref": "main", "qsmxt_ref": ""}


def _rec(res=None, **run):
    return parity.make_record(res, pair="p", phantom="sim", cfg=CFG, manifests=MANIFESTS,
                              run={**RUN, **run}, build={"qsmxt_ref": "main", "qsmxt_commit": "d" * 40})


def test_make_record_says_what_was_checked():
    r = _rec(_parity_json())
    assert r["result"] == "pass" and r["metrics"]["chimap"]["nrmse"] == 1.0
    assert r["qsmrs"] == {"ref": "main", "commit": "c" * 40, "version": "0.40.0"}
    assert r["qsmxt"]["commit"] == "d" * 40
    assert r["candidate"]["digest"] == "sha256:c"            # a local build: its image ID
    assert r["reference"]["digest"] == "sha256:" + "a" * 64   # pinned by algorithm.yml
    assert r["thresholds"] == parity.thresholds_version(CFG, "sim")
    bad = _rec(_parity_json(ok=False, nrmse=3.0))
    assert bad["result"] == "fail" and "nrmse" in bad["failed"][0]
    err = _rec(None)
    assert err["result"] == "error" and err["failed"]


def test_thresholds_version_ignores_bookkeeping():
    v = parity.thresholds_version(CFG, "sim")
    assert parity.thresholds_version({**CFG, "enabled": False, "qsmrs_paths": []}, "sim") == v
    moved = {**CFG, "datasets": {"sim": {**CFG["datasets"]["sim"], "measured": {"x": "run 2"}}}}
    assert parity.thresholds_version(moved, "sim") == v
    tighter = {**CFG, "datasets": {"sim": {"chimap": {"nrmse_max": 1.5}}}}
    assert parity.thresholds_version(tighter, "sim") != v
    assert parity.thresholds_version({**CFG, "candidate_set": {"a": 1}}, "sim") != v


def test_merge_records_is_idempotent_and_drops_baselines():
    a, b = _rec(_parity_json()), _rec(_parity_json(), run_id="2", date="2026-10-29T00:00:00Z")
    base = {**_rec(_parity_json()), "run_id": "0", "result": "baseline"}
    res = parity.merge_records({"checks": []}, [a, base])
    res = parity.merge_records(res, [a, b])
    assert [r["run_id"] for r in res["checks"]] == ["1", "2"]
    assert parity.latest_records(res)[("p", "sim")]["run_id"] == "2"
    many = parity.merge_records({"checks": []}, [{**a, "run_id": str(i), "date": f"2026-10-{i:02d}"}
                                                 for i in range(1, 8)], keep=3)
    assert [r["run_id"] for r in many["checks"]] == ["5", "6", "7"]


ST = {**parity.DEFAULT_SETTINGS}


def _why(rec, cfg=CFG, manifests=MANIFESTS, changes=None, qsmxt_changes=None):
    return parity.staleness(rec, cfg, "sim", manifests, ST, changes, qsmxt_changes)


def test_staleness_rules():
    rec = _rec(_parity_json())
    nothing = lambda c: {"ahead_by": 3, "files": ["src/unwrap/romeo.rs"]}   # noqa: E731
    assert _why(rec, changes=nothing, qsmxt_changes=nothing) == []
    assert _why(None) == ["never checked"]                                       # (d)
    new_ref = {**MANIFESTS, "p-orig": {"image": "ghcr.io/x/orig@sha256:" + "e" * 64}}
    assert "reference image changed" in _why(rec, manifests=new_ref)[0]          # (a)
    hit = lambda c: {"ahead_by": 2, "files": ["src/kernels/dipole.rs", "README.md"]}  # noqa: E731
    w = _why(rec, changes=hit)                                                   # (b)
    assert len(w) == 1 and "src/kernels/dipole.rs" in w[0] and "README" not in w[0]
    gone = lambda c: {"error": "HTTP 404", "unknown_commit": True}               # noqa: E731
    assert "not in" in _why(rec, changes=gone)[0]
    flaky = lambda c: {"error": "timeout"}                                       # noqa: E731
    assert _why(rec, changes=flaky) == []      # a network error is not a staleness verdict
    tighter = {**CFG, "datasets": {"sim": {"chimap": {"nrmse_max": 1.5}}}}
    assert "limits" in _why(rec, cfg=tighter)[0]                                  # (c)
    assert "failed" in _why(_rec(_parity_json(ok=False, nrmse=3)))[0]            # (e)
    assert "without a result" in _why(_rec(None))[0]


def test_no_age_limit():
    """A passing check stands however old it is: only a change makes it stale."""
    old = _rec(_parity_json(), date="2020-01-01T00:00:00Z")
    nothing = lambda c: {"ahead_by": 900, "files": ["docs/x.md"]}   # noqa: E731
    assert _why(old, changes=nothing, qsmxt_changes=nothing) == []
    assert "stale_after_days" not in parity.load_settings()


def test_cargo_lock_makes_every_pair_stale():
    rec = _rec(_parity_json())
    lock = lambda c: {"ahead_by": 1, "files": ["Cargo.lock"]}   # noqa: E731
    w = _why(rec, changes=lock)                                                  # (b), QSM.rs
    assert len(w) == 1 and w[0].startswith("QSM.rs main changed `Cargo.lock`")
    w = _why(rec, qsmxt_changes=lock)                                            # (f), QSMxT
    assert len(w) == 1 and w[0].startswith("QSMxT main changed `Cargo.lock`")
    assert parity.load_settings()["qsmrs_shared_paths"] == ["Cargo.lock"]
    assert parity.load_settings()["qsmxt_shared_paths"] == ["Cargo.lock"]


def test_qsmxt_wiring_rule():
    cfg = {**CFG, "qsmxt_paths": ["src/commands/invert.rs", "crates/qsmxt-engine/src/stages/"]}
    rec = _rec(_parity_json())
    asked = []

    def wiring(c):
        asked.append(c)
        return {"ahead_by": 4, "files": ["crates/qsmxt-engine/src/stages/inversion.rs", "src/tui/ui.rs"]}
    w = _why(rec, cfg=cfg, qsmxt_changes=wiring)                                 # (f)
    assert len(w) == 1 and "stages/inversion.rs" in w[0] and "tui" not in w[0]
    assert asked == ["d" * 40]                     # compared from the QSMxT commit the check built
    tui = lambda c: {"ahead_by": 4, "files": ["src/tui/ui.rs"]}                  # noqa: E731
    assert _why(rec, cfg=cfg, qsmxt_changes=tui) == []
    # A pinned image records no build commit: its `qsmxt --version` gives the release tag.
    pinned = {**rec, "qsmxt": {"ref": None, "commit": None},
              "candidate": {**rec["candidate"], "qsmxt": "qsmxt 10.0.0"}}
    asked.clear()
    _why(pinned, cfg=cfg, qsmxt_changes=wiring)
    assert asked == ["v10.0.0"]
    unknown = {**pinned, "candidate": {"slug": "p-qsmrs"}}
    assert "QSMxT commit of the last check is not recorded" in _why(unknown, cfg=cfg, qsmxt_changes=tui)[0]


def test_pair_status_states_issue_and_table():
    th = {"p": CFG, "q": {"reference": "q-orig", "candidate": "q-qsmrs", "enabled": False,
                          "blocked_by": "astewartau/QSM.rs#319", "datasets": {"sim": {}}},
          "r": {"reference": "r-orig", "candidate": "r-qsmrs", "enabled": False}}
    results = parity.merge_records({"checks": []}, [_rec(_parity_json())])
    rows = parity.pair_status(th, results, MANIFESTS, ST,
                              no_original={"cosmos": {"covers": "COSMOS"}})
    assert [r["state"] for r in rows] == ["current", "gap", "off", "no-original"]
    assert [r["anchor"] for r in rows] == ["pair-p", "pair-q", "pair-r", "pair-cosmos"]

    def doc(**kw):
        return parity.status_doc(th, results, MANIFESTS, ST, today="2026-10-30", release=None,
                                 no_original={"cosmos": {"covers": "COSMOS"}}, **kw)
    md = parity.render_status(doc())
    assert "✅ current" in md and "🚧 gap (astewartau/QSM.rs#319)" in md and "v0.40.0" in md
    assert "| `cosmos` | COSMOS |" in md and "days" not in md
    assert "## Released" in md and "## Development" in md
    # No release known: the released track flags nothing it could run; dev is current.
    assert parity.render_issue(doc()) == ""
    lock = lambda c: {"ahead_by": 1, "files": ["Cargo.lock"]}   # noqa: E731
    d = doc(changes=lock)
    assert d["tracks"]["dev"]["pairs"][0]["state"] == "stale"
    issue = parity.render_issue(d)
    assert "### Development" in issue and "### Released" not in issue
    assert "`p`" in issue and "Cargo.lock" in issue
    assert "gh workflow run parity.yml -R QSMxT/QSM-CI -f algorithm=p -f dataset=configured" in issue


# --- badges ----------------------------------------------------------------------------------------

def _badge(th, recs, **kw):
    results = parity.merge_records({"checks": []}, recs)
    rows = parity.pair_status(th, results, MANIFESTS, ST, **kw)
    return [r["badge"] for r in rows]


def test_badges_per_state():
    two = {**CFG, "datasets": {"sim": CFG["datasets"]["sim"], "kki": CFG["datasets"]["sim"]}}
    sim = _rec(_parity_json(nrmse=0.326), date="2026-10-30T01:00:00Z")
    kki = {**_rec(_parity_json(nrmse=0.05), date="2026-10-29T01:00:00Z", run_id="2"), "dataset": "kki"}
    kki["thresholds"] = parity.thresholds_version(two, "kki")
    sim["thresholds"] = parity.thresholds_version(two, "sim")
    # current: the worst NRMSE over the datasets, dated by the oldest check
    assert _badge({"p": two}, [sim, kki]) == [{"kind": "current", "message": "0.33 % · 29 Oct",
                                               "color": "brightgreen"}]
    same = {**sim, "metrics": {"chimap": {**sim["metrics"]["chimap"], "nrmse": 0.0, "max_abs": 0.0}}}
    assert _badge({"p": CFG}, [{**same, "thresholds": parity.thresholds_version(CFG, "sim")}])[0][
        "message"] == "identical · 30 Oct"
    tiny = {**same, "metrics": {"chimap": {**same["metrics"]["chimap"], "nrmse": 5e-14, "max_abs": 3e-14}},
            "thresholds": parity.thresholds_version(CFG, "sim")}
    assert _badge({"p": CFG}, [tiny])[0]["message"] == "< 0.001 % · 30 Oct"
    lock = lambda c: {"ahead_by": 1, "files": ["Cargo.lock"]}   # noqa: E731
    assert _badge({"p": two}, [sim, kki], changes=lock)[0] == {
        "kind": "stale", "message": "stale · 29 Oct", "color": "orange"}
    bad = _rec(_parity_json(ok=False, nrmse=3), date="2026-10-28T00:00:00Z")
    assert _badge({"p": CFG}, [bad])[0] == {"kind": "failing", "message": "failing · 28 Oct",
                                           "color": "red"}
    assert _badge({"p": CFG}, [])[0] == {"kind": "unchecked", "message": "not yet checked",
                                        "color": "lightgrey"}
    gap = {**CFG, "enabled": False, "blocked_by": "astewartau/QSM.rs#323"}
    assert _badge({"p": gap}, [])[0] == {"kind": "gap", "message": "gap · QSM.rs#323", "color": "yellow"}
    off = {**CFG, "enabled": False}
    assert _badge({"p": off}, [])[0]["message"] == "not enabled"
    assert _badge({}, [], no_original={"cosmos": {}})[0] == {
        "kind": "no-original", "message": "no original", "color": "lightgrey"}


def test_decompose_badge_takes_the_worse_map():
    cfg = {**CFG, "datasets": {"sim": {"chi-para": {"nrmse_max": 6}, "chi-dia": {"nrmse_max": 6},
                                       "measured": {}}}}
    rec = _rec(_parity_json())
    rec["metrics"] = {"chi-para": {"nrmse": 4.9, "max_abs": 0.04}, "chi-dia": {"nrmse": 4.2, "max_abs": 0.03}}
    rec["thresholds"] = parity.thresholds_version(cfg, "sim")
    assert _badge({"p": cfg}, [rec])[0]["message"] == "4.9 % · 28 Oct"


def test_status_and_badges_cli_write_endpoint_files(tmp_path):
    th = tmp_path / "t.yml"
    th.write_text(yaml.safe_dump({"pairs": {"qsmart": parity.load_thresholds()["qsmart"]},
                                  "no_original": {"cosmos": {"covers": "COSMOS"}}}))
    status, badges = tmp_path / "status.json", tmp_path / "badges"
    (badges).mkdir()
    (badges / "gone.json").write_text("{}")
    assert parity.main(["--thresholds", str(th), "status", "--offline", "--today", "2026-10-30",
                        "--latest-release", "v10.0.0",
                        "--results", str(tmp_path / "none.json"), "--json", str(status),
                        "--badges", str(badges)]) == 0
    assert sorted(str(f.relative_to(badges)) for f in badges.rglob("*.json")) == [
        "cosmos.json", "dev/cosmos.json", "dev/not-checked.json", "dev/qsmart.json",
        "not-checked.json", "qsmart.json"]
    b = json.loads((badges / "qsmart.json").read_text())   # the released track: the README's
    assert b == {"schemaVersion": 1, "label": "parity", "message": "not checked · v10.0.0",
                 "color": "lightgrey"}
    assert json.loads((badges / "dev" / "qsmart.json").read_text())["message"] == "not yet checked"
    doc = json.loads(status.read_text())
    assert doc["badges"] == "https://qsmxt.github.io/QSM-CI/parity/badges/"
    assert doc["default_track"] == "released" and doc["tracks"]["released"]["release"] == "v10.0.0"
    assert doc["tracks"]["released"]["release_source"] == "given"
    assert "stale_after_days" not in doc
    out = tmp_path / "site"
    assert parity.main(["badges", "--status", str(status), "--out", str(out)]) == 0
    assert json.loads((out / "cosmos.json").read_text())["message"] == "no original"
    assert json.loads((out / "dev" / "cosmos.json").read_text())["message"] == "no original"


def test_thresholds_paths_and_no_original_are_well_formed():
    import yaml as _y
    doc = _y.safe_load(parity.THRESHOLDS.read_text())
    pairs, none = doc["pairs"], doc.get("no_original") or {}
    assert not set(pairs) & set(none), "a no_original name is also a pair"
    assert not (set(pairs) | set(none)) & set(parity.GENERIC_BADGES)
    for name, cfg in pairs.items():
        for key in ("qsmrs_paths", "qsmxt_paths"):
            paths = cfg.get(key)
            assert isinstance(paths, list) and paths, f"{name}: {key}"
            assert all(isinstance(x, str) and not x.startswith("/") for x in paths), f"{name}: {key}"


def test_report_and_record_cli(tmp_path):
    th = tmp_path / "t.yml"
    th.write_text(yaml.safe_dump({"pairs": {"qsmart": parity.load_thresholds()["qsmart"]}}))
    arts = tmp_path / "arts" / "parity-result-qsmart-sim"
    arts.mkdir(parents=True)
    pj = _parity_json()
    pj.update(algorithm="qsmart", phantom="sim")
    (arts / "parity.json").write_text(json.dumps(pj))
    matrix = json.dumps([{"algorithm": "qsmart", "phantom": "sim"},
                         {"algorithm": "qsmart", "phantom": "s002001-kki-achieva-bridge-run1"}])
    recs, summ = tmp_path / "recs.json", tmp_path / "summary.md"
    assert parity.main(["--thresholds", str(th), "report", "--artifacts", str(tmp_path / "arts"),
                        "--matrix", matrix, "--date", "2026-10-28T00:00:00Z", "--run-id", "7",
                        "--out", str(recs), "--summary", str(summ)]) == 0
    r = json.loads(recs.read_text())
    assert [x["result"] for x in r] == ["pass", "error"]
    s = summ.read_text()
    assert "Release gate: not passed" in s and "`" + "c" * 40 + "`" in s
    results = tmp_path / "results.json"
    assert parity.main(["record", "--records", str(recs), "--results", str(results)]) == 0
    assert parity.main(["record", "--records", str(recs), "--results", str(results)]) == 0
    assert len(json.loads(results.read_text())["checks"]) == 2


def test_run_summary_gate_passes_only_on_one_commit_and_every_enabled_pair():
    ok = _rec(_parity_json())
    assert "Release gate: passed" in parity.render_run_summary([ok], ["p"])
    assert "Release gate: not passed" in parity.render_run_summary([ok], ["p", "other"])
    other = {**ok, "dataset": "kki", "qsmrs": {"commit": "f" * 40}}
    assert "Release gate: not passed" in parity.render_run_summary([ok, other], ["p"])


def test_touched_matches_files_and_directories():
    files = ["src/kernels/dipole.rs", "src/kernelsX.rs", "src/inversion/p.rs"]
    assert parity.touched(files, ["src/kernels/", "src/inversion/p.rs"]) == [
        "src/kernels/dipole.rs", "src/inversion/p.rs"]


def test_multi_output_stage_compares_every_output(tmp_path):
    """χ-separation writes chi-para and chi-dia: both are final maps with their own limits."""
    mask = _mask()
    for side, shift in (("reference", 0.0), ("candidate", 0.5)):
        d = tmp_path / side
        _save(d / "chi-para.nii.gz", np.full((6, 6, 6), 2.0))   # not binary (0/1)
        _save(d / "chi-dia.nii.gz", np.full((6, 6, 6), 2.0) + shift)
    _save(tmp_path / "mask.nii.gz", mask)
    res, _ = parity.compare_dirs(tmp_path / "reference", tmp_path / "candidate",
                                 tmp_path / "mask.nii.gz", ["chi-para", "chi-dia"])
    assert set(res) == {"chi-para", "chi-dia"}
    v = parity.evaluate(res, {"chi-para": {"nrmse_max": 1}}, ["chi-para", "chi-dia"])
    assert v["maps"]["chi-para"]["status"] == "pass"
    assert v["maps"]["chi-dia"]["status"] == "fail" and not v["ok"]   # no limits on a final map


# --- tracks: released (a QSMxT release) and dev (QSMxT main × QSM.rs main) -----------------------

def _rel(res=None, release="v10.0.0", **run):
    """A released-track record: the release's own binary (no qsmrs_ref; qsmxt_ref is the tag)."""
    return parity.make_record(res, pair="p", phantom="sim", cfg=CFG, manifests=MANIFESTS,
                              run={**RUN, "qsmrs_ref": "", "track": "released", "release": release,
                                   **run},
                              build={"qsmxt_ref": release, "qsmxt_commit": "e" * 40,
                                     "qsmrs_version": "0.39.0", "qsmrs_commit": "4" * 40})


def _unavailable(why="QSMxT v10.0.0 has no `qsmxt invert star` (p-qsmrs)"):
    return {"algorithm": "p", "phantom": "sim", "baseline": False, "unavailable": why,
            "provenance": {"candidate": {"steps": [{"slug": "p-qsmrs", "image": "qsmxt-under-test:9",
                                                    "id": "sha256:c", "qsmxt": "qsmxt 10.0.0",
                                                    "qsmrs_version": "0.39.0",
                                                    "qsmrs_commit": "4" * 40}]}}}


def test_records_carry_their_track_and_release():
    assert _rec(_parity_json())["track"] == "dev" and "release" not in _rec(_parity_json())
    r = _rel(_parity_json())
    assert r["track"] == "released" and r["release"] == "v10.0.0"
    assert r["qsmxt"] == {"ref": "v10.0.0", "commit": "e" * 40}
    assert r["qsmrs"]["commit"] == "c" * 40          # what the binary itself reports wins
    u = _rel(_unavailable())
    assert u["result"] == "unavailable" and "invert star" in u["failed"][0]
    assert u["qsmrs"] == {"ref": None, "commit": "4" * 40, "version": "0.39.0"}
    assert "metrics" not in u


def test_existing_results_are_labelled_by_track():
    """parity/results.json: every record names its track; a released one names its release, and a
    dev one was a build of QSMxT main (with qsm-core at QSM.rs main or a release candidate)."""
    for r in parity.load_results()["checks"]:
        assert r.get("track") in parity.TRACKS, r.get("run_id")
        if r["track"] == "released":
            assert r.get("release") and r["qsmxt"]["ref"] == r["release"]
        else:
            assert r["qsmxt"].get("commit") and "release" not in r


def test_released_history_keeps_every_release_dev_keeps_fifty():
    dev = [{**_rec(_parity_json()), "run_id": f"d{i}", "date": f"2026-10-{i:02d}"} for i in range(1, 8)]
    rel = [{**_rel(_parity_json(), release=t), "run_id": f"r{t}", "date": d}
           for t, d in (("v9.22.0", "2026-09-23"), ("v10.0.0", "2026-10-15"), ("v10.1.0", "2026-11-02"))]
    rerun = {**_rel(_parity_json(nrmse=0.5)), "run_id": "again", "date": "2026-11-03"}
    res = parity.merge_records({"checks": []}, dev + rel + [rerun], keep=3)
    kept = [(r["track"], r.get("release"), r["run_id"]) for r in res["checks"]]
    assert [k for k in kept if k[0] == "dev"] == [("dev", None, f"d{i}") for i in (5, 6, 7)]
    # one record per release (a rerun replaces that release's earlier one), every release kept
    assert sorted(k[1:] for k in kept if k[0] == "released") == [
        ("v10.0.0", "again"), ("v10.1.0", "rv10.1.0"), ("v9.22.0", "rv9.22.0")]
    assert parity.recorded_releases(res) == ["v10.1.0", "v10.0.0", "v9.22.0"]
    # a record from before the tracks counts as dev
    old = {k: v for k, v in _rec(_parity_json()).items() if k != "track"}
    assert parity.merge_records({"checks": []}, [old])["checks"][0]["track"] == "dev"
    # the tracks never read each other's records
    assert parity.latest_records(res, "dev")[("p", "sim")]["run_id"] == "d7"
    assert parity.latest_records(res, "released", "v10.1.0")[("p", "sim")]["run_id"] == "rv10.1.0"


def test_release_key_orders_versions():
    tags = ["v10.0.0", "v9.22.0", "v10.0.1", "v10.1.0-rc1", "v10.1.0", "v9.3.0"]
    assert sorted(tags, key=parity.release_key) == [
        "v9.3.0", "v9.22.0", "v10.0.0", "v10.0.1", "v10.1.0-rc1", "v10.1.0"]


def test_released_staleness_only_flags_reference_settings_or_a_missing_run():
    def why(rec, **kw):
        return parity.released_staleness(rec, kw.get("cfg", CFG), "sim", kw.get("m", MANIFESTS),
                                         "v10.0.0")
    assert why(_rel(_parity_json())) == ([], False)
    assert why(_rel(_parity_json(ok=False, nrmse=3))) == ([], False)   # a failure is a result
    assert why(_rel(_unavailable())) == ([], False)                   # so is "not in"
    assert why(None) == (["not run against QSMxT v10.0.0"], True)
    new_ref = {**MANIFESTS, "p-orig": {"image": "ghcr.io/x/orig@sha256:" + "e" * 64}}
    w, rerun = why(_rel(_parity_json()), m=new_ref)
    assert rerun and "reference image changed" in w[0]
    w, rerun = why(_rel(_parity_json()), cfg={**CFG, "datasets": {"sim": {"chimap": {"nrmse_max": 1}}}})
    assert rerun and "settings or limits" in w[0]
    w, rerun = why(_rel(None))
    assert not rerun and "ended without a result" in w[0]   # flagged, never rerun by itself
    assert parity.released_staleness(None, CFG, "sim", MANIFESTS, None) == ([], False)


def _rel_badge(recs, release="v10.0.0", th=None, **kw):
    results = parity.merge_records({"checks": []}, recs)
    rows = parity.pair_status(th or {"p": CFG}, results, MANIFESTS, ST, track="released",
                              release=release, **kw)
    return rows[0]["badge"]


def test_released_badges_name_the_release():
    assert _rel_badge([_rel(_parity_json(nrmse=0.326))]) == {
        "kind": "current", "message": "0.33 % · v10.0.0", "color": "brightgreen"}
    assert _rel_badge([_rel(_parity_json(ok=False, nrmse=3))])["message"] == "failing · v10.0.0"
    assert _rel_badge([_rel(_unavailable())]) == {
        "kind": "unavailable", "message": "not in v10.0.0", "color": "lightgrey"}
    assert _rel_badge([]) == {"kind": "unchecked", "message": "not checked · v10.0.0",
                              "color": "lightgrey"}
    # an older release's result does not count for the latest one
    assert _rel_badge([_rel(_parity_json(), release="v9.22.0")])["message"] == "not checked · v10.0.0"
    new_ref = {**MANIFESTS, "p-orig": {"image": "ghcr.io/x/orig@sha256:" + "e" * 64}}
    rows = parity.pair_status({"p": CFG}, parity.merge_records({"checks": []}, [_rel(_parity_json())]),
                              new_ref, ST, track="released", release="v10.0.0")
    assert rows[0]["badge"]["message"] == "stale · v10.0.0"
    assert rows[0]["refresh"].endswith("-f qsmxt_release=v10.0.0")
    # the dev track's records never show on the released track
    assert _rel_badge([_rec(_parity_json())])["kind"] == "unchecked"


def test_status_doc_history_and_per_release_badges(tmp_path):
    recs = [_rel(_parity_json(ok=False, nrmse=3), release="v9.22.0", run_id="a"),
            _rel(_unavailable(), run_id="b", date="2026-10-29T00:00:00Z"),
            _rec(_parity_json(nrmse=0.2), run_id="c", date="2026-10-31T00:00:00Z")]
    results = parity.merge_records({"checks": []}, recs)
    doc = parity.status_doc({"p": CFG}, results, MANIFESTS, ST, today="2026-11-01",
                            release="v10.0.0", release_source="github")
    rel, dev = doc["tracks"]["released"], doc["tracks"]["dev"]
    assert rel["qsmxt"]["release"] == "v10.0.0" and rel["qsmxt"]["commit"] == "e" * 40
    assert rel["qsmrs"]["commit"] == "4" * 40 and rel["qsmrs"]["version"] == "0.39.0"
    assert rel["pairs"][0]["badge"]["message"] == "not in v10.0.0" and rel["stale"] == []
    assert dev["pairs"][0]["badge"]["message"] == "0.2 % · 31 Oct"
    assert dev["tested"][0]["qsmrs"]["commit"] == "c" * 40
    assert doc["releases"] == ["v10.0.0", "v9.22.0"]
    hist = doc["history"]["p"]
    assert [(e["release"], e["badge"]["message"]) for e in hist] == [
        ("v10.0.0", "not in v10.0.0"), ("v9.22.0", "failing · v9.22.0")]
    assert hist[0]["datasets"][0]["last"]["why"].startswith("QSMxT v10.0.0 has no")
    out = tmp_path / "b"
    written = parity.write_badges(doc, out)
    assert "release/v9.22.0/p.json" in written and "dev/p.json" in written and "p.json" in written
    assert json.loads((out / "release" / "v9.22.0" / "p.json").read_text())["message"] == \
        "failing · v9.22.0"
    md = parity.render_status(doc)
    assert "## Release history" in md and "| `p` | not in v10.0.0 | failing · v9.22.0 |" in md
    assert "QSMxT **v10.0.0**" in md and "⚪ not in v10.0.0" in md
    # the site's deploy rebuilds every badge from the status it serves
    st = tmp_path / "status.json"
    st.write_text(json.dumps(doc))
    site = tmp_path / "site"
    assert parity.main(["badges", "--status", str(st), "--out", str(site)]) == 0
    assert json.loads((site / "release" / "v10.0.0" / "p.json").read_text())["message"] == \
        "not in v10.0.0"


def test_issue_has_a_section_per_flagged_track():
    results = parity.merge_records({"checks": []}, [_rec(_parity_json())])
    doc = parity.status_doc({"p": CFG}, results, MANIFESTS, ST, today="2026-11-01",
                            release="v10.0.0")
    issue = parity.render_issue(doc)
    assert "### Released: QSMxT v10.0.0" in issue and "not run against QSMxT v10.0.0" in issue
    assert "-f qsmxt_release=v10.0.0" in issue and "### Development" not in issue
    results = parity.merge_records(results, [_rel(_parity_json())])
    doc = parity.status_doc({"p": CFG}, results, MANIFESTS, ST, today="2026-11-01",
                            release="v10.0.0")
    assert parity.render_issue(doc) == ""


def test_run_summary_for_a_release():
    recs = [_rel(_parity_json()), {**_rel(_unavailable()), "pair": "q"},
            {**_rel(_parity_json(ok=False, nrmse=3)), "pair": "r"}]
    s = parity.render_run_summary(recs, ["p", "q", "r"])
    assert "Released track: QSMxT **v10.0.0**" in s and "Release gate" not in s
    assert "passed on every dataset run: `p`." in s and "Failed or no result: `r`." in s
    assert "Not in v10.0.0: `q`." in s and "invert star" in s


def test_port_commands_from_run_sh():
    sh = ('#!/bin/bash\n# qsmxt invert ignored "x"\n'
          'if qsmxt invert nltv --help 2>/dev/null | grep -q -- "--magnitude"; then\n'
          '  exec qsmxt invert nltv "$IN/x" -m "$IN/m"\nfi\n'
          'qsmxt qsmart "$IN/totalfield.nii.gz" -o "$OUT/x"\n'
          '    qsmxt r2star "$IN/mag" --echo-times $TES\n'
          'qsmxt separate decompose \\\n  "$IN/a"\n')
    assert parity.port_commands(sh) == [["invert", "nltv"], ["qsmart"], ["r2star"],
                                        ["separate", "decompose"]]


def test_every_port_run_sh_names_a_qsmxt_command():
    for spec in sorted((ROOT / "algorithms").glob("*/algorithm.yml")):
        doc = yaml.safe_load(spec.read_text()) or {}
        if parity.is_port(doc) and (spec.parent / "run.sh").exists():
            assert parity.port_commands((spec.parent / "run.sh").read_text()), spec.parent.name


def test_clap_rejection():
    assert parity.clap_rejection("x\nerror: unrecognized subcommand 'star'\n\n  tip: …") == \
        "unrecognized subcommand 'star'"
    assert parity.clap_rejection("error: unexpected argument '--variant' found\n") == \
        "unexpected argument '--variant' found"
    assert parity.clap_rejection("error: invalid value 'qsmjl' for '--ball <BALL>'") == \
        "invalid value 'qsmjl' for '--ball <BALL>'"
    assert parity.clap_rejection("Traceback …\nValueError: shapes differ") is None
    # the release's command needs an input the port does not pass (qsmxt v10.0.0's paper-based
    # chi-sep-ilsqr and --magnitude, run 41283680804)
    log = ("error: the following required arguments were not provided:\n"
           "  --magnitude <MAGNITUDE>...\n\nUsage: qsmxt separate chi-sep-ilsqr --qsm <QSM> …\n")
    assert parity.clap_rejection(log) == "required argument not provided: --magnitude"


def _th_file(tmp_path):
    th = tmp_path / "t.yml"
    th.write_text(yaml.safe_dump({"pairs": {"star": parity.load_thresholds()["star"]}}))
    return th


def test_unavailable_cli_before_the_run(tmp_path, monkeypatch):
    asked = []

    class R:
        def __init__(self, rc):
            self.returncode, self.stdout, self.stderr = rc, "", ""

    def fake_run(argv, **kw):
        asked.append(argv)
        if "--version" in argv or "inspect" in argv:
            return R(1)
        return R(2 if argv[-3:] == ["invert", "star", "--help"] else 0)
    monkeypatch.setattr(parity.subprocess, "run", fake_run)
    out = tmp_path / "parity.json"
    assert parity.main(["--thresholds", str(_th_file(tmp_path)), "unavailable", "--algorithm", "star",
                        "--release", "v10.0.0", "--qsmrs-image", "rel:1", "--runner", "podman",
                        "--json", str(out)]) == 0
    doc = json.loads(out.read_text())
    assert doc["unavailable"] == "QSMxT v10.0.0 has no `qsmxt invert star` (star-qsmrs)"
    assert asked[0][:2] == ["podman", "run"] and "rel:1" in asked[0]
    # a release that has the command: nothing written, the run goes ahead
    out.unlink()
    monkeypatch.setattr(parity.subprocess, "run", lambda argv, **kw: R(0))
    assert parity.main(["--thresholds", str(_th_file(tmp_path)), "unavailable", "--algorithm", "star",
                        "--release", "v10.0.0", "--qsmrs-image", "rel:1", "--json", str(out)]) == 0
    assert not out.exists()


def test_unavailable_cli_after_a_failed_run(tmp_path):
    log, out = tmp_path / "run.log", tmp_path / "parity.json"
    log.write_text("▸ star-qsmrs: qsm-ci run …\nerror: unexpected argument '--pad' found\n")
    th = _th_file(tmp_path)
    assert parity.main(["--thresholds", str(th), "unavailable", "--algorithm", "star", "--release",
                        "v10.0.0", "--log", str(log), "--json", str(out)]) == 0
    assert "refuses the port's command line: unexpected argument '--pad'" in \
        json.loads(out.read_text())["unavailable"]
    out.unlink()
    log.write_text("subprocess.CalledProcessError: … returned non-zero exit status 137\n")
    assert parity.main(["--thresholds", str(th), "unavailable", "--algorithm", "star", "--release",
                        "v10.0.0", "--log", str(log), "--json", str(out)]) == 0
    assert not out.exists()                      # any other failure stays a failure (an error)


def test_report_cli_on_the_released_track(tmp_path):
    th = _th_file(tmp_path)
    arts = tmp_path / "arts" / "parity-result-star-sim"
    arts.mkdir(parents=True)
    (arts / "parity.json").write_text(json.dumps({**_unavailable(), "algorithm": "star"}))
    recs = tmp_path / "recs.json"
    assert parity.main(["--thresholds", str(th), "report", "--artifacts", str(tmp_path / "arts"),
                        "--matrix", json.dumps([{"algorithm": "star", "phantom": "sim"}]),
                        "--track", "released", "--release", "v10.0.0", "--run-id", "9",
                        "--out", str(recs)]) == 0
    r = json.loads(recs.read_text())[0]
    assert (r["track"], r["release"], r["result"]) == ("released", "v10.0.0", "unavailable")
    with pytest.raises(SystemExit):
        parity.main(["--thresholds", str(th), "report", "--artifacts", str(tmp_path / "arts"),
                     "--matrix", "[]", "--track", "released"])


def test_released_plan(tmp_path, capsys):
    th, results = _th_file(tmp_path), tmp_path / "results.json"
    star = parity.load_thresholds()["star"]
    base = ["--thresholds", str(th), "released-plan", "--offline", "--results", str(results),
            "--latest-release", "v10.1.0"]
    assert parity.main(base) == 0
    plan = json.loads(capsys.readouterr().out)
    assert plan["release"] == "v10.1.0" and plan["algorithm"] == "enabled"
    manifests = parity._manifests()
    recs = [parity.make_record(_unavailable(), pair="star", phantom=ds, cfg=star,
                               manifests=manifests, run={**RUN, "track": "released",
                                                         "release": "v10.1.0"})
            for ds in star["datasets"]]
    results.write_text(json.dumps(parity.merge_records({"checks": []}, recs)))
    assert parity.main(base) == 0
    plan = json.loads(capsys.readouterr().out)
    assert plan["algorithm"] == ""                      # the release's result stands
    moved = {**recs[0], "reference": {**recs[0]["reference"], "digest": "sha256:" + "0" * 64}}
    results.write_text(json.dumps(parity.merge_records({"checks": []}, [moved] + recs[1:])))
    assert parity.main(base) == 0
    plan = json.loads(capsys.readouterr().out)
    assert plan["algorithm"] == "star" and "reference image changed" in plan["why"]


def test_release_without_an_optional_feed_reruns_the_candidate_without_it(tmp_path, monkeypatch):
    """Released track: qsmxt v10.0.0 has no `qsmart --reliability`, so the QSMART pair reruns the
    candidate without that optional feed (the total field is still fed), and the record and badge
    say so; a pair without an optional feed has nothing to drop."""
    import argparse
    import subprocess as sp
    calls = []

    def fake(argv, env=None, check=False, **kw):
        if argv[:2] == ["qsm-ci", "run"]:
            calls.append(argv)
            out = Path(argv[argv.index("-o") + 1])
            _save(out, np.zeros((4, 4, 4)))
            if argv[2].endswith("qsmart-matlab"):
                inter = Path(argv[argv.index("--intermediates") + 1])
                _save(inter / "tfs.nii.gz", np.full((4, 4, 4), 0.5))
                _save(inter / "R_0.nii.gz", np.ones((4, 4, 4)))
        return sp.CompletedProcess(argv, 1, "", "")

    monkeypatch.setattr(parity.subprocess, "run", fake)
    assert parity.optional_feeds(parity.load_thresholds()["qsmart"], "sim") == ["reliability"]
    assert parity.optional_feeds(parity.load_thresholds()["tkd"], "sim") == []
    work = tmp_path / "w"
    args = argparse.Namespace(thresholds=parity.THRESHOLDS, algorithm="qsmart", phantom="sim",
                              dataset=str(_qsmart_ds(tmp_path)), work=str(work), runner="docker",
                              qsmrs_image="rel:1", candidate_only=False, drop_optional_feeds=False)
    assert parity.cmd_run(args) == 0 and "--reliability" in calls[-1]
    calls.clear()
    args.candidate_only = args.drop_optional_feeds = True
    assert parity.cmd_run(args) == 0
    assert len(calls) == 1 and calls[0][2].endswith("qsmart-qsmrs")    # the reference is not rerun
    assert "--reliability" not in calls[0] and "--totalfield" in calls[0]
    assert json.loads((work / "candidate" / parity.DROPPED).read_text()) == ["reliability"]
    # compare carries it into parity.json, the record and the badge
    pj = tmp_path / "parity.json"
    parity.main(["compare", "--algorithm", "qsmart", "--phantom", "sim", "--dataset",
                 str(tmp_path / "ds"), "--work", str(work), "--json", str(pj)])
    res = json.loads(pj.read_text())
    assert res["dropped_feeds"] == ["reliability"] and "without the optional feed" in res["note"]
    cfg = parity.load_thresholds()["qsmart"]
    rec = parity.make_record(res, pair="qsmart", phantom="sim", cfg=cfg, manifests=parity._manifests(),
                             run={**RUN, "track": "released", "release": "v10.0.0"})
    assert rec["dropped_feeds"] == ["reliability"]
    row = {"state": "current", "datasets": [{"last": parity._summary(rec, ["chimap"])}]}
    assert parity.badge(row, "released", "v10.0.0")["message"].endswith(" · v10.0.0 · no reliability")
    # nothing to drop, or no reference to rerun against: exit 3, nothing run
    calls.clear()
    tkd = argparse.Namespace(**{**vars(args), "algorithm": "tkd"})
    assert parity.cmd_run(tkd) == 3 and not calls
    fresh = argparse.Namespace(**{**vars(args), "work": str(tmp_path / "empty")})
    assert parity.cmd_run(fresh) == 3 and not calls


def test_rejected_setting_names_the_candidate_set_key():
    cfg = {"reference": "a", "candidate": "b", "candidate_set": {"offset_grid": "qsmart-reference",
                                                                 "grid": "native"},
           "datasets": {"sim": {"candidate_set": {"variant": "qsmjl"}}}}
    log = "x\nerror: unexpected argument '--qsmart-offset-grid' found\n"
    assert parity.rejected_setting(cfg, "sim", log) == "offset_grid"   # the longest match wins
    assert parity.rejected_setting(cfg, "sim", "error: invalid value 'qsmjl' for '--variant <V>'") \
        == "variant"
    assert parity.rejected_setting(cfg, "sim", "error: unexpected argument '--reliability' found") is None
    assert parity.rejected_setting(cfg, "sim", "error: unrecognized subcommand 'star'") is None
    assert parity.rejected_setting(cfg, "sim", "error: the following required arguments were not "
                                   "provided:\n  --qsmart-offset-grid <G>\n") is None
    assert parity.rejected_setting(cfg, "sim", "Traceback: boom") is None


def test_release_without_a_candidate_setting_reruns_the_candidate_without_it(tmp_path, monkeypatch):
    """After the optional feeds, a `candidate_set` setting the release's qsmxt refuses (QSMART's
    offset_grid on v10.0.0) is dropped too; record and badge name both, the reference is not rerun."""
    import argparse
    import subprocess as sp
    calls = []

    def fake(argv, env=None, check=False, **kw):
        if argv[:2] == ["qsm-ci", "run"]:
            calls.append(argv)
            out = Path(argv[argv.index("-o") + 1])
            _save(out, np.zeros((4, 4, 4)))
            if argv[2].endswith("qsmart-matlab"):
                inter = Path(argv[argv.index("--intermediates") + 1])
                _save(inter / "tfs.nii.gz", np.full((4, 4, 4), 0.5))
                _save(inter / "R_0.nii.gz", np.ones((4, 4, 4)))
        return sp.CompletedProcess(argv, 1, "", "")

    monkeypatch.setattr(parity.subprocess, "run", fake)
    work = tmp_path / "w"
    args = argparse.Namespace(thresholds=parity.THRESHOLDS, algorithm="qsmart", phantom="sim",
                              dataset=str(_qsmart_ds(tmp_path)), work=str(work), runner="docker",
                              qsmrs_image="rel:1", candidate_only=False, drop_optional_feeds=False,
                              drop_setting=None)
    assert parity.cmd_run(args) == 0
    assert "offset_grid=qsmart-reference" in calls[-1]
    calls.clear()
    args.candidate_only = args.drop_optional_feeds = True
    args.drop_setting = ["offset_grid", "not_a_setting"]
    assert parity.cmd_run(args) == 0
    assert len(calls) == 1 and calls[0][2].endswith("qsmart-qsmrs")
    assert "--reliability" not in calls[0] and "offset_grid=qsmart-reference" not in calls[0]
    assert json.loads((work / "candidate" / parity.DROPPED_SETTINGS).read_text()) == ["offset_grid"]
    pj = tmp_path / "parity.json"
    parity.main(["compare", "--algorithm", "qsmart", "--phantom", "sim", "--dataset",
                 str(tmp_path / "ds"), "--work", str(work), "--json", str(pj)])
    res = json.loads(pj.read_text())
    assert res["dropped_settings"] == ["offset_grid"] and "candidate setting" in res["note"]
    rec = parity.make_record(res, pair="qsmart", phantom="sim", cfg=parity.load_thresholds()["qsmart"],
                             manifests=parity._manifests(),
                             run={**RUN, "track": "released", "release": "v10.0.0"})
    assert rec["dropped_feeds"] == ["reliability"] and rec["dropped_settings"] == ["offset_grid"]
    row = {"state": "current", "datasets": [{"last": parity._summary(rec, ["chimap"])}]}
    assert parity.badge(row, "released", "v10.0.0")["message"].endswith(
        " · v10.0.0 · no reliability, no offset_grid")
    # nothing to drop (tkd has no optional feed and no such setting): exit 3, nothing run
    none = argparse.Namespace(**{**vars(args), "algorithm": "tkd", "drop_setting": None})
    calls.clear()
    assert parity.cmd_run(none) == 3 and not calls


def test_rejected_setting_cli(tmp_path, capsys):
    log = tmp_path / "run.log"
    log.write_text("error: unexpected argument '--qsmart-offset-grid' found\n")
    assert parity.main(["rejected-setting", "--algorithm", "qsmart", "--log", str(log)]) == 0
    assert capsys.readouterr().out.strip() == "offset_grid"
    log.write_text("error: unexpected argument '--reliability' found\n")
    assert parity.main(["rejected-setting", "--algorithm", "qsmart", "--log", str(log)]) == 0
    assert capsys.readouterr().out.strip() == ""


def test_released_plan_selects_every_enabled_pair_without_a_record(tmp_path, capsys):
    """A pair with no released record for the current release is due, whatever ran before: another
    pair's records (e.g. a run that only reached some pairs) do not make the release 'run'."""
    th = tmp_path / "t.yml"
    real = parity.load_thresholds()
    th.write_text(yaml.safe_dump({"pairs": {"star": real["star"], "tkd": real["tkd"]}}))
    results = tmp_path / "results.json"
    star = [parity.make_record(_unavailable(), pair="star", phantom=ds, cfg=real["star"],
                               manifests=parity._manifests(),
                               run={**RUN, "track": "released", "release": "v10.0.0"})
            for ds in real["star"]["datasets"]]
    # tkd ran on one dataset only
    tkd_ds = sorted(real["tkd"]["datasets"])
    tkd = [parity.make_record(_parity_json(), pair="tkd", phantom=tkd_ds[0], cfg=real["tkd"],
                              manifests=parity._manifests(),
                              run={**RUN, "track": "released", "release": "v10.0.0"})]
    base = ["--thresholds", str(th), "released-plan", "--offline", "--results", str(results),
            "--latest-release", "v10.0.0"]
    results.write_text(json.dumps(parity.merge_records({"checks": []}, star)))
    assert parity.main(base) == 0
    assert json.loads(capsys.readouterr().out)["algorithm"] == "tkd"     # never ran at all
    if len(tkd_ds) > 1:
        results.write_text(json.dumps(parity.merge_records({"checks": []}, star + tkd)))
        assert parity.main(base) == 0
        assert json.loads(capsys.readouterr().out)["algorithm"] == "tkd"   # missing a dataset
    # records for an older release, or the dev track, never count for this one
    old = [{**r, "release": "v9.22.0"} for r in star]
    results.write_text(json.dumps(parity.merge_records({"checks": []}, old + [_rec(_parity_json())])))
    assert parity.main(base) == 0
    assert json.loads(capsys.readouterr().out)["algorithm"] == "enabled"


def test_released_busy_ignores_cancelled_and_cancelling_runs():
    runs = [
        {"id": 1, "display_title": "parity · released v10.0.0 · enabled", "status": "in_progress"},
        {"id": 2, "display_title": "parity · released v10.0.0 · enabled", "status": "in_progress"},
        {"id": 3, "display_title": "parity · released v10.0.0 · enabled", "status": "completed",
         "conclusion": "cancelled"},
        {"id": 4, "display_title": "parity · released v10.0.0 · enabled", "status": "queued"},
        {"id": 5, "display_title": "parity · released v10.0.01 · enabled", "status": "queued"},
        {"id": 6, "display_title": "parity · enabled", "status": "in_progress"},
        {"id": 7, "display_title": "parity · released v10.0.0 · tkd", "status": "completed",
         "conclusion": "success"},
    ]
    jobs = {1: [{"conclusion": "success"}, {"conclusion": None}],
            2: [{"conclusion": "success"}, {"conclusion": "cancelled"}]}   # being cancelled
    assert parity.active_release_runs(runs, "v10.0.0", lambda i: jobs.get(i, [])) == [1, 4]
    assert parity.active_release_runs([], "v10.0.0", lambda i: []) == []


def test_a_cancelled_parity_run_records_nothing():
    """parity.yml's record job: never for a cancelled run (its unfinished jobs would be recorded
    as errors, and count as the release's run)."""
    wf = yaml.safe_load((ROOT / ".github" / "workflows" / "parity.yml").read_text())
    cond = wf["jobs"]["record"]["if"]
    assert "!cancelled()" in cond and "always()" not in cond
