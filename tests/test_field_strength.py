"""`field_strength:` — a method trained for one B0 is never composed on a phantom at another.

R2PRIMEnet-7T's R2′ on a 3 T phantom is out of distribution: QSMxT refuses that route, and on
ridani-3t-aniso-fitted it drove chisep-ilsqr to its 2 h cap (DNF, score run 41577320951). The GRE-only
grid (pipeline.run_chisep_composed) now leaves those pairs out, scripts/prune_inapplicable.py drops
the rows scored before the rule, and declaring the field needs no rescore.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import prune_inapplicable as pi  # noqa: E402
import score_plan as sp  # noqa: E402


def test_field_strength_parsing_and_matching(pipeline):
    assert pipeline._field_strength({}, "m") is None
    assert pipeline._field_strength({"field_strength": 7}, "m") == 7.0
    assert pipeline._field_strength({"field_strength": 2.89}, "m") == 2.89
    for bad in ("7T", True, 0, -3, [7]):
        with pytest.raises(SystemExit, match="field_strength"):
            pipeline._field_strength({"field_strength": bad}, "m")
    assert pipeline.field_matches(None, 3.0) and pipeline.field_matches(7.0, None)   # undeclared / unknown B0
    assert pipeline.field_matches(7.0, 7.0) and pipeline.field_matches(7.0, 6.98)
    assert not pipeline.field_matches(7.0, 3.0) and not pipeline.field_matches(3.0, 7.0)


def test_phantom_b0_comes_from_the_registry_and_is_checked_against_params(pipeline, tmp_path, monkeypatch, capsys):
    reg = {"p3": {"track": "chisep", "field_strength": 3}, "pu": {"track": "chisep"}}
    (tmp_path / "reg.json").write_text(json.dumps(reg))
    monkeypatch.setenv("QSMCI_DATASETS_FILE", str(tmp_path / "reg.json"))
    params = tmp_path / "params.json"
    params.write_text(json.dumps({"B0": 3.0}))
    assert pipeline.phantom_field_strength("p3", params) == 3.0
    assert pipeline.phantom_field_strength("pu", params) == 3.0                 # registry silent → params.json
    assert pipeline.phantom_field_strength(None, params) == 3.0                 # local run without --phantom
    assert pipeline.phantom_field_strength("pu", tmp_path / "missing.json") is None
    assert "::warning::" not in capsys.readouterr().out
    params.write_text(json.dumps({"B0": 7.0}))
    assert pipeline.phantom_field_strength("p3", params) == 3.0                 # registry wins, but says so
    assert "disagrees with params.json B0 7.0" in capsys.readouterr().out


def _grid(pipeline, monkeypatch, tmp_path, b0):
    """Run the GRE-only grid with stubbed generators / χ-sep runs; return the (gen, sep) pairs run."""
    (tmp_path / "params.json").write_text(json.dumps({"B0": b0}))
    monkeypatch.delenv("QSMCI_DATASETS_FILE", raising=False)
    ran_gens, ran_pairs = [], []

    def r2gen(g, args, src):
        ran_gens.append(g["slug"])
        return (g["slug"], tmp_path / "r2p.nii.gz", 1.0, [])

    def composed(task, args, src, gt, mask, cache):
        ran_pairs.append((task[0], task[1]["slug"]))
        return {"id": f"{task[0]}~{task[1]['slug']}", "status": "ok"}
    monkeypatch.setattr(pipeline, "do_r2gen", r2gen)
    monkeypatch.setattr(pipeline, "do_chisep_composed", composed)
    algo = lambda slug, stage, fs=None, consumes=("r2prime",): {  # noqa: E731
        "slug": slug, "stage": stage, "field_strength": fs, "consumes": list(consumes)}
    algos = [algo("gen", "r2prime-generation"), algo("gen-7t", "r2prime-generation", 7.0),
             algo("sep", "chi-separation"), algo("sep-7t", "chi-separation", 7.0)]
    args = SimpleNamespace(focus=None, shard=None, phantom=None, inputs="gt", runs_out=tmp_path / "r.json")
    runs: list = []
    pipeline.run_chisep_composed(args, algos, {"params": tmp_path / "params.json"}, None, None, runs)
    return set(ran_gens), set(ran_pairs), runs


def test_the_gre_only_grid_leaves_out_off_field_methods(pipeline, monkeypatch, tmp_path, capsys):
    gens, pairs, runs = _grid(pipeline, monkeypatch, tmp_path, 3.0)
    assert gens == {"gen"} and pairs == {("gen", "sep")}                 # the 7 T generator never even runs
    assert all(r["status"] == "ok" for r in runs) and len(runs) == 1     # no DNF rows for the skipped pairs
    out = capsys.readouterr().out
    assert "not applicable: generator gen-7t is trained for 7 T only and this phantom is 3 T" in out
    assert "not applicable: χ-separation method sep-7t" in out
    gens, pairs, _ = _grid(pipeline, monkeypatch, tmp_path, 7.0)
    assert gens == {"gen", "gen-7t"} and len(pairs) == 4                 # at 7 T: the full grid


def test_r2primenet_7t_declares_7t_and_every_chisep_phantom_its_b0():
    spec = yaml.safe_load((ROOT / "algorithms" / "r2primenet-7t" / "algorithm.yml").read_text())
    assert spec["field_strength"] == 7
    reg = json.loads((ROOT / "scripts" / "datasets.json").read_text())
    for k, v in reg.items():
        if v.get("track") != "chisep":
            continue
        assert isinstance(v.get("field_strength"), (int, float)), k
        m = re.search(r"(\d(?:\.\d)?)\s?T\b", v["label"])                # the label names the field
        if m:
            assert float(m.group(1)) == v["field_strength"], k


# --------------------------------------------------------------------------------------------- prune

REG = {"meso-3t": {"track": "chisep", "field_strength": 3}, "wm-micro-7t": {"track": "chisep", "field_strength": 7},
       "nob0": {"track": "chisep"}}
FIELDS = {"r2primenet-7t": 7.0}


def _row(rid, phantom, gen="r2primenet-7t", sep="chisep-medi", mode="composed"):
    r = {"id": rid, "phantom": phantom, "mode": mode, "status": "ok"}
    if mode == "composed":
        r["combo"] = {"r2prime_generation": gen, "chi_separation": sep}
    return r


def test_prune_drops_only_composed_rows_off_their_methods_field():
    runs = [_row("a", "meso-3t"), _row("b", "wm-micro-7t"), _row("c", "meso-3t", gen="r2primenet"),
            _row("d", "meso-3t", mode="isolated"), _row("e", "nob0"), _row("f", None)]
    keep, dropped = pi.prune(runs, REG, FIELDS)
    assert [r["id"] for r in keep] == ["b", "c", "d", "e", "f"]
    assert dropped == [("a", "r2primenet-7t is trained for 7 T, phantom meso-3t is 3 T")]
    assert pi.prune(keep, REG, FIELDS) == (keep, [])                     # idempotent


def test_prune_reads_the_real_declarations_and_the_cli_rewrites_in_place(tmp_path):
    assert pi.declared_field_strengths(ROOT / "algorithms")["r2primenet-7t"] == 7.0
    idx = tmp_path / "index.json"
    idx.write_text(json.dumps({"generated": None, "runs": [_row("a", "meso-3t"), _row("b", "wm-micro-7t")]}))
    cmd = [sys.executable, str(ROOT / "scripts" / "prune_inapplicable.py"), str(idx)]
    assert subprocess.run(cmd + ["--check"], capture_output=True).returncode == 1
    out = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
    assert "not applicable, dropped: a" in out
    assert [r["id"] for r in json.loads(idx.read_text())["runs"]] == ["b"]
    assert idx.read_text().endswith("}\n")                               # merge_index.py's format
    assert subprocess.run(cmd + ["--check"], capture_output=True).returncode == 0


def test_declaring_field_strength_needs_no_rescore_and_merge_prunes():
    assert "field_strength" in sp.SCORE_COSMETIC
    wf = (ROOT / ".github" / "workflows" / "score.yml").read_text()
    commit = wf[wf.index("Commit results index + scoring state"):]
    assert commit.index("scripts/merge_index.py") < commit.index("python3 scripts/prune_inapplicable.py results/index.json") \
        < commit.index("git add results/index.json")
