"""Submission well-formedness gate (fast, static — no container).

A malformed submission — missing `run.sh`, a typo'd `run:` path, a missing required field, an
unknown `stage` — otherwise merges green: evaluate.yml runs the container but swallows the
resulting DNF, so the breakage only shows up as a DNF on the leaderboard *after* merge. This test
fails the PR instead, in seconds, with a specific message. (Pullability of the image is gated
separately by the image-access workflow; the runtime behaviour by evaluate.yml.)
"""
import shlex
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent

# Valid stage names = the swappable stages + the named spans, straight from the registry.
_STAGES_YML = yaml.safe_load((ROOT / "stages.yml").read_text())
VALID_STAGES = set(_STAGES_YML.get("stages", {})) | set(_STAGES_YML.get("spans", {}))

REQUIRED_FIELDS = ("name", "slug", "stage", "image", "run")
# Sources that carry a codebase reimplementation of a generic technique — these get tagged into the
# slug (algorithm-source). Branded/unique published methods (any other source) stay bare.
_TAGGED_SOURCES = {"qsmrs", "sti", "cornell", "qsmci"}
_INTERPRETERS = {"bash", "sh", "python", "python3", "env"}


def _submission_dirs():
    for d in sorted((ROOT / "algorithms").glob("*/")):
        if d.name.startswith("_"):          # _template etc. are not submissions
            continue
        if (d / "algorithm.yml").exists():
            yield d


@pytest.mark.parametrize("d", list(_submission_dirs()), ids=lambda d: d.name)
def test_submission_is_wellformed(d):
    meta = yaml.safe_load((d / "algorithm.yml").read_text())
    assert isinstance(meta, dict), f"{d.name}: algorithm.yml is not a mapping"

    for field in REQUIRED_FIELDS:
        assert meta.get(field), f"{d.name}: algorithm.yml missing required field '{field}'"

    assert meta["stage"] in VALID_STAGES, (
        f"{d.name}: unknown stage {meta['stage']!r} (valid: {sorted(VALID_STAGES)})"
    )

    # Slug must equal the dir name and the derived taxonomy id, so naming can't drift:
    # generic techniques (source in the tagged set) -> algorithm[-variant]-source; branded -> algorithm.
    assert meta["slug"] == d.name, f"{d.name}: slug {meta['slug']!r} must equal the directory name"
    algorithm, source, variant = meta.get("algorithm"), meta.get("source"), meta.get("variant")
    assert algorithm and source, f"{d.name}: algorithm.yml needs 'algorithm' and 'source' fields"
    parts = [algorithm] + ([variant] if variant else []) + ([source] if source in _TAGGED_SOURCES else [])
    assert meta["slug"] == "-".join(parts), (
        f"{d.name}: slug {meta['slug']!r} != derived {'-'.join(parts)!r} "
        f"(algorithm={algorithm}, variant={variant}, source={source})"
    )

    # The `run:` command must reference a script that actually exists in the submission dir
    # (this is what catches a missing/renamed/typo'd run.sh — the exact class of merge-green,
    # score-DNF bug this gate exists for).
    tokens = shlex.split(str(meta["run"]))
    candidates = [t for t in tokens if not t.startswith("-") and t not in _INTERPRETERS]
    assert any((d / t).exists() for t in candidates), (
        f"{d.name}: run {meta['run']!r} references no existing file in the submission dir "
        f"(looked for {candidates})"
    )
