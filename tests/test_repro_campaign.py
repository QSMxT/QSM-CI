"""The harmonization campaign (scripts/repro_campaign.yml): its parity versions and authors' chains.

The committed campaign must load (every method exists, every preset names a parameter its base
declares). derive() gives each parity version its base's container with the preset, which run_algo
passes as --set overrides. A field-mapping variant's `chain` keeps it to one authors' pipeline in the
REAL plan_composed: its columns, dipoles and spans are only the chain's, every shard agrees, and the
other field maps keep the whole matrix.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import repro_campaign  # noqa: E402

TRACK = "repro"


def test_committed_campaign_loads():
    c = repro_campaign.load()
    assert c["variants"] and c["methods"]["field-mapping"] == ["romeo-qsmrs", "laplacian-qsmrs"]


def _row(pipeline, slug, stage, **extra):
    return {"slug": slug, "stage": stage, "name": slug, "dir": Path("algorithms") / slug,
            "consumes": pipeline.STAGES[stage]["consumes"],
            "produces": pipeline.STAGES[stage]["produces"], **extra}


@pytest.fixture
def campaign(tmp_path):
    """A small campaign over fixture algorithm folders: two field maps, two bfrs, two dipoles, a
    span, a bfr parity version and a field-mapping variant chained to one bfr and one dipole."""
    algs = tmp_path / "algorithms"
    for slug, stage, params in [("fm-a", "field-mapping", ["solver"]), ("fm-b", "field-mapping", []),
                                ("bfr-a", "bfr", ["radius"]), ("bfr-b", "bfr", []),
                                ("dip-a", "dipole", []), ("dip-b", "dipole", []),
                                ("span-a", "bfr+dipole", [])]:
        (algs / slug).mkdir(parents=True)
        (algs / slug / "algorithm.yml").write_text(yaml.safe_dump(
            {"slug": slug, "stage": stage, "parameters": [{"name": p, "default": 1} for p in params]}))
    doc = {"methods": {"field-mapping": ["fm-a", "fm-b"], "bfr": ["bfr-a", "bfr-b"],
                       "dipole": ["dip-a", "dip-b"], "bfr+dipole": ["span-a"]},
           "variants": {
               "bfr-a.p": {"base": "bfr-a", "label": "parity", "set": {"radius": 3}},
               "fm-a.x": {"base": "fm-a", "label": "authors", "set": {"solver": True},
                          "chain": {"bfrs": ["bfr-a.p"], "dipoles": ["dip-b"], "spans": []}}}}
    path = tmp_path / "campaign.yml"
    path.write_text(yaml.safe_dump(doc))
    return path, algs


def test_derive_gives_each_variant_its_base_with_the_preset(pipeline, campaign):
    path, algs = campaign
    c = repro_campaign.load(path, algs)
    base = [_row(pipeline, s, st) for s, st in [("fm-a", "field-mapping"), ("fm-b", "field-mapping"),
                                                ("bfr-a", "bfr"), ("bfr-b", "bfr"), ("dip-a", "dipole"),
                                                ("dip-b", "dipole"), ("span-a", "bfr+dipole"),
                                                ("not-in-campaign", "dipole")]]
    out = {a["slug"]: a for a in repro_campaign.derive(base, c)}
    assert "not-in-campaign" not in out
    assert out["bfr-a.p"]["dir"] == out["bfr-a"]["dir"] and out["bfr-a.p"]["preset"] == {"radius": "3"}
    assert out["fm-a.x"]["preset"] == {"solver": "true"}      # booleans as the wrappers' jq reads them
    assert out["fm-a.x"]["chain"]["dipoles"] == {"dip-b"}


def test_a_chain_keeps_its_field_map_to_one_pipeline(pipeline, campaign):
    path, algs = campaign
    c = repro_campaign.load(path, algs)
    base = [_row(pipeline, s, st) for s, st in [("fm-a", "field-mapping"), ("fm-b", "field-mapping"),
                                                ("bfr-a", "bfr"), ("bfr-b", "bfr"), ("dip-a", "dipole"),
                                                ("dip-b", "dipole"), ("span-a", "bfr+dipole")]]
    algos = repro_campaign.derive(base, c)
    p = pipeline.plan_composed(algos, None, TRACK, None, None)
    pipes = {(t, b, d["slug"]) for (t, b) in p.col_owner for d in p.dipole if p.composes(d, t, b)}
    assert {x for x in pipes if x[0] == "fm-a.x"} == {("fm-a.x", "bfr-a.p", "dip-b")}
    # the other field maps keep the whole matrix, the parity version included
    assert len({x for x in pipes if x[0] == "fm-b"}) == 3 * 2
    assert ("fm-a.x", "span-a") not in p.span_owner and ("fm-b", "span-a") in p.span_owner
    # every column is owned by exactly one shard, and a chain's excluded column by none
    owners = [{k for k in p.col_owner
               if pipeline.plan_composed(algos, None, TRACK, i, 3).owns_col(*k)} for i in range(3)]
    assert set().union(*owners) == set(p.col_owner) and sum(map(len, owners)) == len(p.col_owner)
    assert not any(pipeline.plan_composed(algos, None, TRACK, i, 3).owns_col("fm-a.x", "bfr-b")
                   for i in range(3))


def test_a_preset_must_name_a_declared_parameter(campaign):
    path, algs = campaign
    doc = yaml.safe_load(path.read_text())
    doc["variants"]["bfr-a.p"]["set"] = {"radiuss": 3}
    path.write_text(yaml.safe_dump(doc))
    with pytest.raises(SystemExit, match="declares no parameter 'radiuss'"):
        repro_campaign.load(path, algs)


def test_run_algo_passes_the_preset_under_explicit_overrides(pipeline, monkeypatch, tmp_path):
    seen = {}
    monkeypatch.setattr(pipeline, "cli_run_argv", lambda algo, i, o, af, runner, ov: seen.setdefault("ov", ov) or ["true"])
    monkeypatch.setattr(pipeline, "_wait", lambda *a, **k: None)
    monkeypatch.setattr(pipeline.subprocess, "Popen", lambda *a, **k: None)
    algo = {"slug": "bfr-a.p", "preset": {"radius": "3", "tol": "1e-3"}, "produces": ["localfield"]}
    pipeline.run_algo(algo, tmp_path / "in", tmp_path / "out", "apptainer", {"tol": "1e-6"})
    assert seen["ov"] == {"radius": "3", "tol": "1e-6"}


def test_a_span_takes_an_optional_input_when_there_is_one(pipeline, monkeypatch, tmp_path):
    """A composed span (QSMART) runs without its optional reliability map, and takes the one its
    field map wrote beside the total field (QSMART's echo fit) when there is one."""
    seen = []

    def fake_run(algo, idir, odir, runner, overrides=None):
        seen.append(sorted(p.name for p in idir.iterdir()))
        odir.mkdir(parents=True, exist_ok=True)
        return 0.0
    monkeypatch.setattr(pipeline, "run_algo", fake_run)
    monkeypatch.setattr(pipeline, "collect", lambda *a, **k: {"status": "ok", "metrics": {}})
    span = _row(pipeline, "qsmart-x", "bfr+dipole", optional=["reliability"])
    span["consumes"] = span["consumes"] + ["reliability"]
    fm_dir = tmp_path / "fm"; fm_dir.mkdir()
    for name in ("totalfield.nii.gz", "mask.nii.gz", "magnitude.nii.gz", "params.json"):
        (fm_dir / name).write_text("x")
    gt_sources = {a: fm_dir / pipeline.ARTIFACT_FILE[a] for a in ("mask", "magnitude", "params")}
    tf_sources = {"fm": (fm_dir / "totalfield.nii.gz", fm_dir / "mask.nii.gz", 0.0, [])}
    args = type("A", (), {"work": tmp_path / "w", "runner": "local", "track": TRACK,
                          "emit_volumes": False, "phantom_sfx": ""})()
    pipeline.do_span((span, "fm"), args, gt_sources, None, fm_dir / "mask.nii.gz", tf_sources)
    (fm_dir / "reliability.nii.gz").write_text("r")
    pipeline.do_span((span, "fm"), args, gt_sources, None, fm_dir / "mask.nii.gz", tf_sources)
    assert "reliability.nii.gz" not in seen[0] and "reliability.nii.gz" in seen[1]
