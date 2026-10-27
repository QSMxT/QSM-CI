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
    assert all(r["ok"] for r in parity.check(m, lim))


# --- pairs / matrix -----------------------------------------------------------------------------

def test_discover_pairs_needs_an_original_and_a_port(tmp_path):
    for slug, alg, src in (("x-orig", "x", "vendor"), ("x-qsmrs", "x", "qsmrs"),
                           ("y-a-qsmrs", "y", "qsmrs"), ("y-b-qsmrs", "y", "qsmrs"),
                           ("z-orig", "z", "vendor")):
        (tmp_path / slug).mkdir()
        (tmp_path / slug / "algorithm.yml").write_text(
            yaml.safe_dump({"algorithm": alg, "source": src, "stage": "dipole"}))
    assert parity.discover_pairs(tmp_path) == {"x": {"original": ["x-orig"], "port": ["x-qsmrs"]}}


def test_real_thresholds_name_real_pairs():
    """Every configured pair must exist in algorithm.yml with those two slugs on the right sides."""
    pairs, th = parity.discover_pairs(), parity.load_thresholds()
    assert th.get("qsmart", {}).get("enabled"), "the QSMART pair is the one enabled today"
    for alg, cfg in th.items():
        assert alg in pairs, alg
        assert cfg["reference"] in pairs[alg]["original"], alg
        assert cfg["candidate"] in pairs[alg]["port"], alg
        for ds, dcfg in (cfg.get("datasets") or {}).items():
            assert ds in json.loads((ROOT / "scripts" / "datasets.json").read_text()), ds
            for side in ("reference", "candidate"):
                for slug in (dcfg or {}).get(f"{side}_prefix") or []:
                    assert (ROOT / "algorithms" / slug / "algorithm.yml").exists(), slug
            for key, lim in (dcfg or {}).items():
                if key in ("chimap",):
                    parity.check({}, lim)                    # well-formed limit keys
            for lim in ((dcfg or {}).get("intermediates") or {}).values():
                parity.check({}, lim)


def test_plan_matrix():
    th = {"a": {"enabled": True, "datasets": {"sim": {}, "kki": {}}},
          "b": {"enabled": False, "datasets": {"sim": {}}}}
    assert parity.plan_matrix(th, "enabled", "configured") == [
        {"algorithm": "a", "phantom": "kki"}, {"algorithm": "a", "phantom": "sim"}]
    assert parity.plan_matrix(th, "b", "sim") == [{"algorithm": "b", "phantom": "sim"}]
    assert parity.plan_matrix(th, "a", "other") == [{"algorithm": "a", "phantom": "other"}]
    with pytest.raises(SystemExit):
        parity.plan_matrix(th, "nope", "sim")


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
