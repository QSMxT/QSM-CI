"""The dataset/phantom registry (scripts/datasets.json) and its pipeline.py consumers.

The registry is the single source of truth for every scoring dataset: score.yml's plan job expands
chi-separation methods across its active chisep-track phantoms, fetch_dataset.sh resolves OSF
files/pack flags from it, pipeline.py namespaces run ids by phantom with it, and gen_manifest.py
embeds it in web/algorithms.json for the site. These tests pin its shape (so a malformed entry fails
here, not mid-rescore) and the id-suffix / tuned-parameter fallback semantics that keep existing
published run ids stable.
"""
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

_spec = importlib.util.spec_from_file_location("pipeline", ROOT / "scripts" / "pipeline.py")
pipeline = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pipeline)


def _registry() -> dict:
    return json.loads((ROOT / "scripts" / "datasets.json").read_text())


# ---- registry shape --------------------------------------------------------------------------

def test_registry_entries_are_well_formed():
    reg = _registry()
    assert reg, "registry is empty"
    for ph, d in reg.items():
        assert d.get("track"), f"{ph}: missing track"
        assert d.get("label"), f"{ph}: missing label"
        assert d.get("path"), f"{ph}: missing path"
        assert d.get("osf_file") or d.get("osf_env"), \
            f"{ph}: needs osf_file (literal id) and/or osf_env (secret name)"


def test_exactly_one_default_phantom_per_track():
    reg = _registry()
    tracks = {d["track"] for d in reg.values()}
    for t in tracks:
        defaults = [k for k, d in reg.items() if d["track"] == t and d.get("default")]
        assert len(defaults) == 1, f"track {t}: expected exactly one default phantom, got {defaults}"
        assert reg[defaults[0]].get("active"), f"track {t}: default phantom {defaults[0]} is inactive"


def test_legacy_track_args_are_registry_keys():
    # sim/invivo are both a track name AND their track's default phantom id, so callers that pass
    # the bare track name keep working. (The chisep track's default is a named phantom, chisep-mc,
    # since the original single 'chisep' phantom was retired.)
    reg = _registry()
    for legacy in ("sim", "invivo"):
        assert legacy in reg, f"legacy phantom id '{legacy}' missing from the registry"
        assert reg[legacy]["track"] == legacy


# ---- pipeline.py: id namespacing ------------------------------------------------------------

def test_default_phantoms_keep_legacy_ids():
    # The default phantom of every track adds NO id suffix — existing published run ids survive.
    reg = _registry()
    assert pipeline.phantom_suffix(None) == ""
    for ph, d in reg.items():
        if d.get("default"):
            assert pipeline.phantom_suffix(ph) == "", f"default phantom {ph} must not suffix ids"


def test_non_default_phantom_suffixes_ids(tmp_path, monkeypatch):
    reg = _registry()
    reg["ridani-3t-iso"] = {"track": "chisep", "label": "Ridani 3T iso",
                            "osf_env": "OSF_FILE_RIDANI_3T_ISO",
                            "path": "data/ridani-3t-iso/scoring", "active": True}
    f = tmp_path / "datasets.json"
    f.write_text(json.dumps(reg))
    monkeypatch.setenv("QSMCI_DATASETS_FILE", str(f))
    assert pipeline.phantom_suffix("ridani-3t-iso") == "-ridani-3t-iso"
    assert pipeline.phantom_suffix("chisep-mc") == ""       # the chisep-track default keeps bare ids
    assert pipeline.default_phantom("chisep") == "chisep-mc"  # default phantom of the chisep track


def test_unknown_phantom_raises():
    with pytest.raises(KeyError):
        pipeline.phantom_suffix("nope-not-a-phantom")


# ---- pipeline.py: tuned-parameter fallback ---------------------------------------------------

DOC = {"parameters": [
    {"name": "lam", "default": 1, "tuned": {"chisep": 2, "ridani-3t-iso": 3}},
    {"name": "mu", "default": 4, "tuned": 5},                       # legacy scalar = sim only
    {"name": "tol", "default": 6, "tuned": {"sim": 7, "invivo": 8}},
]}


def test_tuned_exact_phantom_key_wins():
    assert pipeline._tuned_overrides(DOC, "chisep", "ridani-3t-iso") == {"lam": "3"}


def test_tuned_falls_back_to_track_key():
    # A phantom with no tuned entry of its own inherits the track-family tuning.
    assert pipeline._tuned_overrides(DOC, "chisep", "ridani-7t-aniso") == {"lam": "2"}
    assert pipeline._tuned_overrides(DOC, "chisep") == {"lam": "2"}


def test_tuned_legacy_scalar_is_sim_only():
    assert pipeline._tuned_overrides(DOC, "sim") == {"mu": "5", "tol": "7"}
    assert pipeline._tuned_overrides(DOC, "sim", "sim") == {"mu": "5", "tol": "7"}
    assert pipeline._tuned_overrides(DOC, "invivo") == {"tol": "8"}
