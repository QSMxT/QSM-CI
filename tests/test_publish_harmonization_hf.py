"""scripts/publish_harmonization_hf.py: wiring a Hugging Face copy into the registry text."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("phf", ROOT / "scripts" / "publish_harmonization_hf.py")
phf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(phf)

REG = '''{
  "a": {
    "track": "repro",
    "input_levels": ["l3"],
    "osf_file": "x"
  },
  "b": {
    "track": "repro",
    "osf_file": "y"
  }
}
'''


def test_wire_adds_fields_and_keeps_formatting():
    out = phf.wire_registry(REG, "a", "org/repo", "qsmci-inputs/a.zip", "ab" * 32)
    d = json.loads(out)
    assert d["a"]["hf_repo"] == "org/repo" and d["a"]["hf_path"] == "qsmci-inputs/a.zip"
    assert d["a"]["sha256"] == "ab" * 32 and "hf_repo" not in d["b"]
    assert '"input_levels": ["l3"]' in out  # hand-kept inline list survives


def test_rewiring_replaces_not_duplicates():
    once = phf.wire_registry(REG, "a", "org/repo", "qsmci-inputs/a.zip", "ab" * 32)
    twice = phf.wire_registry(once, "a", "org/repo", "qsmci-inputs/a.zip", "cd" * 32)
    assert twice.count('"sha256"') == 1 and json.loads(twice)["a"]["sha256"] == "cd" * 32
