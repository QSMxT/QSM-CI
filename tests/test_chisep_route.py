"""The χ-separation toolbox route is shared by two entries: their copies must stay identical."""
from pathlib import Path

ALG = Path(__file__).resolve().parents[1] / "algorithms"


def test_chisep_route_copies_identical():
    a = (ALG / "chisepnet" / "chisep_route.py").read_bytes()
    b = (ALG / "qsmnetme" / "chisep_route.py").read_bytes()
    assert a == b, "algorithms/chisepnet/chisep_route.py and algorithms/qsmnetme/chisep_route.py differ"
