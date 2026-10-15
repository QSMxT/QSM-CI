"""`qsm_ci/qsm_eval.py` and `eval/qsm_eval.py` must be the same scorer.

There is one scorer in this repo, reachable by two paths: `eval/qsm_eval.py` is what the CI invokes
as a script (and what `eval/test_metrics.py` imports), while `qsm_ci/qsm_eval.py` is what ships in
the wheel and what `qsm-ci run --truth` imports, so local numbers match the leaderboard. They are
kept identical by a git symlink — which is exactly why this needs a test: a checkout with
`core.symlinks=false` (Windows without developer mode, some CI images, an export through a tool that
flattens links) materialises the link as a one-line TEXT file holding "../eval/qsm_eval.py". That
imports fine as an empty module and every metric silently disappears.

Content is compared rather than asserting `islink`, so an honest copy (or a future build step that
copies instead of linking) passes too; only a divergence or a stub fails.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACKAGED = ROOT / "qsm_ci" / "qsm_eval.py"
CANONICAL = ROOT / "eval" / "qsm_eval.py"


def test_both_scorer_paths_exist():
    assert CANONICAL.is_file(), f"the canonical scorer is missing: {CANONICAL}"
    assert PACKAGED.is_file(), f"the packaged scorer is missing: {PACKAGED}"


def test_the_packaged_scorer_is_byte_identical_to_the_canonical_one():
    """If this fails after an edit, change `eval/qsm_eval.py` and let the link follow — do not fix
    it by editing the copy, which is how the two paths start scoring differently."""
    assert PACKAGED.read_bytes() == CANONICAL.read_bytes(), (
        f"{PACKAGED} diverged from {CANONICAL} (a checkout with core.symlinks=false replaces it "
        "with a one-line text file containing the link target)")


def test_the_packaged_scorer_is_not_a_flattened_symlink_stub():
    """The specific failure mode, named: a stub is a single short line naming the target."""
    text = PACKAGED.read_text()
    assert len(text.splitlines()) > 1
    assert text.strip() != "../eval/qsm_eval.py"


def test_the_packaged_scorer_actually_exposes_the_metrics():
    """Belt and braces on the import path the CLI uses: a stub would import cleanly and expose none
    of these, so every `qsm-ci run --truth` score would be an AttributeError."""
    from qsm_ci import qsm_eval

    for name in ("load", "correlation", "xsim", "nrmse_challenge", "hfen", "score_arrays"):
        assert callable(getattr(qsm_eval, name, None)), f"qsm_ci.qsm_eval.{name} is missing"
