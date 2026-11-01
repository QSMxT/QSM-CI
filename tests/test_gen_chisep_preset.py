"""scripts/gen_chisep_preset.py: the χ-separation datasets are regenerated from a pinned qsm-forward
preset and packed — wiring only (the phantom physics is qsm-forward's and tested there). Nothing here
runs qsm-forward: its module is replaced by a stub that records the call."""
from __future__ import annotations

import importlib
import json
import re
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
gcp = importlib.import_module("gen_chisep_preset")


def _registry() -> dict:
    return json.loads((ROOT / "scripts" / "datasets.json").read_text())


def test_every_active_chisep_dataset_is_a_pinned_qsm_forward_preset():
    reg = _registry()
    active = [k for k, d in reg.items() if d["track"] == "chisep" and d.get("active")]
    assert active, "no active chisep dataset"
    for k in active:
        g = gcp.generator(k)
        assert re.fullmatch(r"[0-9a-f]{7,40}", g["ref"]), f"{k}: ref must be a commit, got {g['ref']!r}"


def test_all_chisep_generators_share_one_pin():
    # One qsm-forward commit builds the whole benchmark tier, so the datasets are comparable.
    refs = {d["generator"]["ref"] for d in _registry().values() if d.get("generator")}
    assert len(refs) == 1, refs


def test_generator_refuses_unknown_and_ungenerated_phantoms():
    with pytest.raises(SystemExit, match="unknown phantom"):
        gcp.generator("no-such-phantom")
    with pytest.raises(SystemExit, match="no generator block"):
        gcp.generator("chisep-mc")   # retired; built by gen_chisep.py, not a preset


def test_check_pin(monkeypatch):
    monkeypatch.setattr(gcp, "installed_ref", lambda: "5e79235abcdef")
    gcp.check_pin("5e79235")                      # prefix match passes
    with pytest.raises(SystemExit, match="pins 1234567"):
        gcp.check_pin("1234567")
    gcp.check_pin("1234567", allow_unpinned=True)  # warns, continues
    monkeypatch.setattr(gcp, "installed_ref", lambda: None)
    with pytest.raises(SystemExit, match="not a git install"):
        gcp.check_pin("5e79235")


def test_preset_overrides_pass_only_known_keys():
    assert gcp.preset_overrides({"preset": "ridani-3t-aniso", "r2prime_source": "fitted", "wm_rois": True}) \
        == {"r2prime_source": "fitted"}
    assert gcp.preset_overrides({"preset": "meso-3t"}) == {}
    assert gcp.preset_overrides({"preset": "meso-3t", "degrade_levels": ["L3"]}) == {"degrade_levels": ("L3",)}


@pytest.fixture
def stub_qsm_forward(monkeypatch):
    calls = {}
    chisep = types.SimpleNamespace(
        preset=lambda name, **ov: ("cfg", name, ov),
        generate_chisep_bids=lambda data, bids, cfg, wm_rois=None: calls.update(
            data=data, bids=bids, cfg=cfg, wm_rois=wm_rois) or {},
    )
    mod = types.ModuleType("qsm_forward"); mod.chisep = chisep
    monkeypatch.setitem(sys.modules, "qsm_forward", mod)
    monkeypatch.setitem(sys.modules, "qsm_forward.chisep", chisep)
    return calls


def test_main_generates_the_registry_preset_and_packs(stub_qsm_forward, monkeypatch, tmp_path):
    packed = {}
    monkeypatch.setattr(gcp, "installed_ref", lambda: _registry()["ridani-3t-aniso-fitted"]["generator"]["ref"])
    monkeypatch.setattr(gcp, "pack", lambda bids, out, ridani: packed.update(bids=bids, out=out, ridani=ridani))
    gcp.main(["ridani-3t-aniso-fitted", "--qsmf-data", str(tmp_path / "head"),
              "--wm-rois-src", str(tmp_path / "rois.nii.gz"), "--out", str(tmp_path / "out"),
              "--bids", str(tmp_path / "bids")])
    assert stub_qsm_forward["cfg"] == ("cfg", "ridani-3t-aniso",
                                       {"r2prime_source": "fitted", "degrade_levels": ("L3",)})
    assert stub_qsm_forward["bids"] == str(tmp_path / "bids")
    assert stub_qsm_forward["wm_rois"] == str(tmp_path / "rois.nii.gz")
    assert packed == {"bids": tmp_path / "bids", "out": tmp_path / "out", "ridani": True}


def test_main_needs_the_wm_atlas_when_the_dataset_ships_wm_rois(stub_qsm_forward, monkeypatch, tmp_path):
    monkeypatch.setattr(gcp, "installed_ref", lambda: _registry()["meso-3t"]["generator"]["ref"])
    monkeypatch.setattr(gcp, "pack", lambda *a, **k: None)
    with pytest.raises(SystemExit, match="--wm-rois-src"):
        gcp.main(["meso-3t", "--qsmf-data", str(tmp_path), "--out", str(tmp_path / "out"),
                  "--bids", str(tmp_path / "bids")])


def test_main_refuses_an_unpinned_generator(stub_qsm_forward, monkeypatch, tmp_path):
    monkeypatch.setattr(gcp, "installed_ref", lambda: "0000000")
    with pytest.raises(SystemExit, match="pip install"):
        gcp.main(["meso-3t", "--qsmf-data", str(tmp_path), "--out", str(tmp_path / "out")])


def test_rekey_retired_default_is_idempotent(tmp_path):
    import importlib.util
    spec = importlib.util.spec_from_file_location("rekey", ROOT / "scripts/oneoff/rekey_retired_chisep_default.py")
    rk = importlib.util.module_from_spec(spec); spec.loader.exec_module(rk)
    idx = {"runs": [{"id": "wavesep-iso", "phantom": "chisep-mc"},
                    {"id": "wavesep-iso-ridani-3t-iso", "phantom": "ridani-3t-iso"},
                    {"id": "hc-iso-chisep-mc", "phantom": "chisep-mc"},
                    {"id": "tkd-iso"}]}
    (tmp_path / "index.json").write_text(json.dumps(idx))
    (tmp_path / "wavesep-iso").mkdir()
    rk.main(["--results", str(tmp_path)])
    ids = [r["id"] for r in json.loads((tmp_path / "index.json").read_text())["runs"]]
    assert ids == ["wavesep-iso-chisep-mc", "wavesep-iso-ridani-3t-iso", "hc-iso-chisep-mc", "tkd-iso"]
    assert (tmp_path / "wavesep-iso-chisep-mc").is_dir() and not (tmp_path / "wavesep-iso").exists()
    rk.main(["--results", str(tmp_path)])             # second run: nothing left to move
    assert [r["id"] for r in json.loads((tmp_path / "index.json").read_text())["runs"]] == ids
