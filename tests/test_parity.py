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


ARTIFACTS = ("chimap", "localfield", "totalfield", "chi-para", "chi-dia")


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


def _why(rec, cfg=CFG, manifests=MANIFESTS, today="2026-10-30", changes=None):
    st = {"stale_after_days": 90, "qsmrs_repo": "astewartau/QSM.rs", "qsmrs_branch": "main"}
    return parity.staleness(rec, cfg, "sim", manifests, st, today, changes)


def test_staleness_rules():
    rec = _rec(_parity_json())
    nothing = lambda c: {"ahead_by": 3, "files": ["src/unwrap/romeo.rs"]}   # noqa: E731
    assert _why(rec, changes=nothing) == []
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
    assert "days ago" in _why(rec, today="2027-02-28")[0]                         # (d)
    assert "failed" in _why(_rec(_parity_json(ok=False, nrmse=3)))[0]            # (e)
    assert "without a result" in _why(_rec(None))[0]


def test_pair_status_states_issue_and_table():
    th = {"p": CFG, "q": {"reference": "q-orig", "candidate": "q-qsmrs", "enabled": False,
                          "blocked_by": "astewartau/QSM.rs#319", "datasets": {"sim": {}}},
          "r": {"reference": "r-orig", "candidate": "r-qsmrs", "enabled": False}}
    results = parity.merge_records({"checks": []}, [_rec(_parity_json())])
    st = {"stale_after_days": 90, "qsmrs_repo": "astewartau/QSM.rs", "qsmrs_branch": "main"}
    rows = parity.pair_status(th, results, MANIFESTS, st, "2026-10-30")
    assert [r["state"] for r in rows] == ["current", "gap", "off"]
    assert parity.render_issue(rows, st, "2026-10-30") == ""
    md = parity.render_status(rows, st, "2026-10-30")
    assert "✅ current" in md and "🚧 gap (astewartau/QSM.rs#319)" in md and "v0.40.0" in md
    rows = parity.pair_status(th, results, MANIFESTS, st, "2027-06-01")
    assert rows[0]["state"] == "stale"
    issue = parity.render_issue(rows, st, "2027-06-01")
    assert "`p`" in issue and "days ago" in issue
    assert "gh workflow run parity.yml -R QSMxT/QSM-CI -f algorithm=p -f dataset=configured" in issue


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
