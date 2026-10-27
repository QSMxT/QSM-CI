"""The Julia-original submissions share one piece of glue, qsmci_io.jl.

Each submission folder is mounted on its own at /algo, so every Julia submission carries a copy of
algorithms/_julia/qsmci_io.jl. This keeps the copies identical, so a fix lands in all of them.
"""
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CANONICAL = ROOT / "algorithms" / "_julia" / "qsmci_io.jl"
COPIES = sorted((ROOT / "algorithms").glob("*/qsmci_io.jl"))


@pytest.mark.parametrize("copy", [c for c in COPIES if c != CANONICAL], ids=lambda p: p.parent.name)
def test_qsmci_io_copy_is_identical(copy):
    assert copy.read_bytes() == CANONICAL.read_bytes(), (
        f"{copy.parent.name}/qsmci_io.jl differs from algorithms/_julia/qsmci_io.jl; "
        "edit the canonical file and copy it to every Julia submission"
    )
