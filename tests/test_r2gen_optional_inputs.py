"""An R2′ generator's `optional_inputs:` on the GRE-only path (pipeline.do_r2gen).

R2PRIMEnet (QSM.rs) declares `optional_inputs: [r2star]` (port parity feeds the original's R2*). No
dataset ships an R2*, and do_r2gen called prepare_input without the optional list, so every
generator run raised "missing source artifact 'r2star'" and all its GRE-only combos were DNF (score
run 44225121850: 78 rows). The isolated path (do_isolated) already passed it.
"""
from __future__ import annotations

from types import SimpleNamespace


def test_r2gen_skips_a_missing_optional_input(pipeline, tmp_path, monkeypatch):
    src = {}
    for art in ("magnitude", "mask", "params"):
        p = tmp_path / pipeline.ARTIFACT_FILE[art]
        p.write_text(art)
        src[art] = p

    def fake_run(a, idir, odir, runner, *rest):
        assert sorted(f.name for f in idir.iterdir()) == ["magnitude.nii.gz", "mask.nii.gz", "params.json"]
        odir.mkdir(parents=True, exist_ok=True)
        (odir / pipeline.ARTIFACT_FILE["r2prime"]).write_text("r2p")
        return 1.0

    monkeypatch.setattr(pipeline, "run_algo", fake_run)
    g = {"slug": "gen", "consumes": ["magnitude", "mask", "params", "r2star"], "optional": ["r2star"]}
    args = SimpleNamespace(work=tmp_path / "work", runner="docker")
    res = pipeline.do_r2gen(g, args, src)
    assert not isinstance(res, pipeline.Failed), res
    assert res[0] == "gen" and res[1].name == "r2prime.nii.gz"
