"""The harmonization payloads' binary columnar layout (scripts/repro_format.py).

Each harmonization cohort (REPRO_GROUPS: the EMTP traveling heads, the MGH pilot) has its own
results/<stem>.json and results/<stem>_regions.json, small JSON indexes; the per-pair fit stats and
the per-run regional χ live beside them as float32 columns. These pin that the layout loses nothing:
every value the old all-JSON payload stored comes back bit-identical through the reader, the index
and the files agree on shape and content, a stale or truncated file is refused rather than read as
wrong numbers, and no cohort's payload holds, counts or ranks anything of another's.
"""
import json
import math
import random
from pathlib import Path

import pytest

import repro_eval
import repro_format as rf

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"


def _nan_eq(x, y):
    return x == y or (x != x and y != y)


def test_columns_round_trip_exactly_at_their_decimals(tmp_path):
    rng = random.Random(3)
    dec = {"slope": 4, "bias": 6, "n": 0, "chi": 1}
    n = 2000
    cols = {"slope": [round(rng.uniform(-1, 3), 4) for _ in range(n)],
            "bias": [round(rng.uniform(-3, 3), 6) for _ in range(n)],
            "n": [rng.randrange(0, 26) for _ in range(n)],
            "chi": [round(rng.uniform(-3000, 3000), 1) for _ in range(n)]}
    for c in cols.values():                                  # missing values, both spellings
        c[5], c[17] = None, float("nan")
    desc = rf.write_columns(tmp_path, [("a.bin", {"slope": cols["slope"], "bias": cols["bias"]}),
                                       ("b.bin", {"n": cols["n"], "chi": cols["chi"]})], (40, 50), dec)
    assert desc["shape"] == [40, 50] and [f["fields"] for f in desc["files"]] == [["slope", "bias"], ["n", "chi"]]
    assert (tmp_path / "a.bin").stat().st_size == 2 * 4 * n
    back = rf.read_columns(tmp_path / "index.json", desc)
    for f, vals in cols.items():
        want = [float("nan") if v is None else v for v in vals]
        assert all(_nan_eq(float(x), y) for x, y in zip(want, back[f])), f
    assert set(rf.read_columns(tmp_path / "index.json", desc, ["n"])) == {"n"}   # only what was asked


def test_reader_refuses_a_stale_or_truncated_file(tmp_path):
    desc = rf.write_columns(tmp_path, [("a.bin", {"x": [1.5] * 12})], (3, 4), {"x": 1})
    data = (tmp_path / "a.bin").read_bytes()
    (tmp_path / "a.bin").write_bytes(data[:-4])
    with pytest.raises(ValueError, match="stale or truncated"):
        rf.read_columns(tmp_path / "i.json", desc)
    (tmp_path / "a.bin").write_bytes(b"\0" * len(data))
    with pytest.raises(ValueError, match="stale or truncated"):
        rf.read_columns(tmp_path / "i.json", desc)


def _cohort_acqs(group):
    return {k: a for k, a in repro_eval.repro_acquisitions().items() if a["group"] == group}


@pytest.mark.parametrize("group", list(rf.REPRO_GROUPS))
def test_fits_reproduce_every_per_pair_value_exactly(repro_payload, group):
    """What load_repro() gives back is what the old payload stored: _pair_metrics' rounded values
    (|a-1| included, now derived from the slope), the summaries, and the rejections — over this
    cohort's comparisons only."""
    out, rois = repro_payload
    doc = rf.load_repro(out / rf.payload_names(group)["repro"])
    acqs = _cohort_acqs(group)
    plan = repro_eval.comparison_plan(acqs)
    assert doc["group"] == group and set(doc["acquisitions"]) == set(acqs)
    assert list(doc["pipelines"]) == sorted(p for p in rois if "retired-bfr" not in p
                                            and any(a in acqs for a in rois[p]))
    n_fit = 0
    for p, node in doc["pipelines"].items():
        rejected = []
        for cls, grp, key, a, b in plan:
            va, vb = rois[p].get(a), rois[p].get(b)
            got = node[cls].get(grp, {}).get(key)
            if not va or not vb:
                assert got is None
                continue
            m, rej = repro_eval._pair_metrics(va, vb)
            if rej:
                rejected.append({"class": cls, "group": grp, "pair": key, **rej})
            assert got.keys() == (m or {}).keys() if got else m is None
            if m:
                n_fit += 1
                assert all(_nan_eq(got[f], m[f]) for f in m), (p, cls, grp, key)
                assert type(got["n_rois"]) is int
        assert node["rejected"] == rejected
        devs = [m["abs_slope_dev"] for c in rf.CLASSES for g in node[c].values() for m in g.values()]
        assert node["n_rejected"] == len(rejected) and node["n_possible"] == len(plan)
        assert sum(node[f"{c}_n_pairs"] for c in rf.CLASSES) == len(devs)
        for c in rf.CLASSES:
            assert node[f"{c}_n_possible"] == sum(1 for x in plan if x[0] == c)
    whys = {r["why"] for n in doc["pipelines"].values() for r in n["rejected"]}
    assert whys == {"slope_cap", "flat_roi_cloud", "too_few_rois"} and n_fit > 50
    assert doc["pipelines"]["laplacian-qsmrs+pdf-qsmrs+tv-qsmrs"]["n_no_recon"] > 0


def test_cohorts_are_isolated(repro_payload):
    """No acquisition, pair, target or regional run of one cohort appears in another's payload, and
    together the cohorts cover every comparison and every run exactly once."""
    out, rois = repro_payload
    acqs = repro_eval.repro_acquisitions()
    all_pairs, all_runs = set(), set()
    for group in rf.REPRO_GROUPS:
        names = rf.payload_names(group)
        idx = json.loads((out / names["repro"]).read_text())
        mine = set(_cohort_acqs(group))
        assert idx["group"] == group and set(idx["acquisitions"]) == mine
        assert all(p["a"] in mine and p["b"] in mine for p in idx["pairs"])
        assert set(idx["targets"].values()) <= mine
        assert {f["file"] for f in idx["fits"]["files"]} == set(names["fits"])
        pairs = {(p["a"], p["b"]) for p in idx["pairs"]}
        assert not pairs & all_pairs
        all_pairs |= pairs
        reg = json.loads((out / names["regions"]).read_text())
        assert reg["group"] == group and set(reg["acqs"]) <= mine and set(reg["acquisitions"]) <= mine
        assert set(reg["targets"].values()) <= mine
        assert reg["values"]["files"][0]["file"] == names["regions_bin"]
        runs = {(r["p"], r["a"]) for r in rf.load_regions(out / names["regions"])["runs"]}
        assert not runs & all_runs
        all_runs |= runs
    plan = repro_eval.comparison_plan(acqs)
    assert all_pairs == {(a, b) for *_, a, b in plan}
    assert all_runs == {(p, a) for p, by in rois.items() if "retired-bfr" not in p for a in by}
    # a pipeline that only ran on the traveling heads is in their payload and not the pilot's
    heads = json.loads((out / rf.payload_names("harmonization")["repro"]).read_text())["pipelines"]
    pilot = json.loads((out / rf.payload_names("harmonization-pilot")["repro"]).read_text())["pipelines"]
    assert "tgv-qsmrs" in heads and "tgv-qsmrs" not in pilot


@pytest.mark.parametrize("group", list(rf.REPRO_GROUPS))
def test_regions_reproduce_every_run_value(repro_payload, group):
    out, rois = repro_payload
    names = rf.payload_names(group)
    doc = rf.load_regions(out / names["regions"])
    idx = json.loads((out / names["regions"]).read_text())
    assert idx["values"]["shape"] == [len(idx["pipelines"]), len(idx["acqs"]), len(idx["structures"])]
    got = {(r["p"], r["a"]): r["m"] for r in doc["runs"]}
    mine = _cohort_acqs(group)
    want = {(p, a) for p, by in rois.items() if "retired-bfr" not in p for a in by if a in mine}
    assert set(got) == want
    groups = {"Putamen": (12, 51), "Brain-Stem": (16,)}
    for (p, a), m in got.items():
        for st, ids in groups.items():
            vals = [(rois[p][a][i], 100 + i) for i in ids if i in rois[p][a]]
            if vals:   # the n-weighted L/R mean in ppb, 1 dp: the value the old run list carried
                assert m[st] == round(sum(v * n for v, n in vals) / sum(n for _, n in vals) * 1000, 1)


def test_payload_names_are_the_committed_files():
    """The traveling heads keep the original names (results/repro.json & co.), the pilot gets its own
    stem, and every payload file is whitelisted for the workflows to commit."""
    assert rf.payload_names("harmonization") == {
        "repro": "repro.json", "fits": ["repro_fits.bin", "repro_fits_extra.bin"],
        "regions": "repro_regions.json", "regions_bin": "repro_regions.bin"}
    assert rf.payload_names("harmonization-pilot")["repro"] == "repro_pilot.json"
    keys = [g["key"] for g in rf.REPRO_GROUPS.values()]
    stems = [g["stem"] for g in rf.REPRO_GROUPS.values()]
    assert len(set(keys)) == len(keys) and len(set(stems)) == len(stems)
    assert list(rf.REPRO_GROUPS)[0] == rf.DEFAULT_GROUP and rf.REPRO_GROUPS[rf.DEFAULT_GROUP]["key"] == "repro"
    for name in rf.all_payload_names():
        assert (RESULTS / name).exists(), name


def _check_index(index_path: Path, desc: dict, shape):
    assert desc["dtype"] == rf.DTYPE and desc["shape"] == list(shape)
    n = math.prod(shape)
    for f in desc["files"]:
        assert f["bytes"] == 4 * n * len(f["fields"]) == (index_path.parent / f["file"]).stat().st_size
    return rf.read_columns(index_path, desc)          # also verifies every sha256


@pytest.mark.parametrize("group", list(rf.REPRO_GROUPS))
def test_committed_repro_payload_is_consistent(group):
    path = RESULTS / rf.payload_names(group)["repro"]
    idx = json.loads(path.read_text())
    assert idx["group"] == group
    pairs, pipes = idx["pairs"], idx["pipelines"]
    assert len(pipes) == len(set(pipes)) and pipes == sorted(pipes)
    cols = _check_index(path, idx["fits"], (len(pipes), len(pairs)))
    assert set(cols) == set(rf.FIT_DECIMALS) and idx["fits"]["decimals"] == rf.FIT_DECIMALS
    assert [f["file"] for f in idx["fits"]["files"]] == rf.payload_names(group)["fits"]
    # `pairs` and `comparisons` describe the same comparisons, every one between known acquisitions
    flat = {(p["class"], p["group"], p["key"]): [p["a"], p["b"]] for p in pairs}
    assert flat == {(c, g, k): ab for c, gs in idx["comparisons"].items() for g, ks in gs.items() for k, ab in ks.items()}
    assert all(p["a"] in idx["acquisitions"] and p["b"] in idx["acquisitions"] for p in pairs)
    # ... and exactly this cohort's acquisitions
    assert set(idx["acquisitions"]) == set(_cohort_acqs(group))
    assert set(idx["summary"]) == set(rf.SUMMARY_FIELDS)
    assert all(len(v) == len(pipes) for v in idx["summary"].values())
    assert all(n == len(pairs) for n in idx["summary"]["n_possible"])   # only this cohort's pairs
    assert set(idx["rejected"]) <= set(pipes)
    assert all(0 <= r["pair"] < len(pairs) for rs in idx["rejected"].values() for r in rs)
    # a pipeline's fitted-pair count per class is its count of non-NaN slopes in that class
    s = cols["slope"]
    for i in range(0, len(pipes), 37):
        for c in rf.CLASSES:
            n = sum(1 for j, p in enumerate(pairs) if p["class"] == c and s[i * len(pairs) + j] == s[i * len(pairs) + j])
            assert n == idx["summary"][f"{c}_n_pairs"][i]
    assert len(json.dumps(idx)) < 300_000          # the index stays small; the bulk is in the .bin files


@pytest.mark.parametrize("group", list(rf.REPRO_GROUPS))
def test_committed_regions_payload_is_consistent(group):
    path = RESULTS / rf.payload_names(group)["regions"]
    idx = json.loads(path.read_text())
    assert idx["group"] == group
    shape = (len(idx["pipelines"]), len(idx["acqs"]), len(idx["structures"]))
    cols = _check_index(path, idx["values"], shape)
    assert set(idx["acqs"]) <= set(_cohort_acqs(group)) and set(idx["acquisitions"]) <= set(_cohort_acqs(group))
    assert any(v == v for v in cols["chi_ppb"])
