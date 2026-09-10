"""Human-facing docs name submissions that exist.

The algorithm slug renames (structured taxonomy, PR #137) left `qsm-ci run sharp`,
`algorithms/matlab-tkd`, `cd algorithms/chi-sepnet`, … in the README, the docs, the site, the CLI
docstring, the per-submission BUILD.md files and the .gitignore's Dockerfile patterns — every one a
slug or folder that no longer exists (issues #193, #220, #222). The set of folders under algorithms/
is the authority. These tests grep the prose for `qsm-ci run <slug>`, `algorithms/<slug>` and
`--pipeline a,b,c`, and the .gitignore for `algorithms/<folder>/…` patterns, and fail on any name
that isn't a real submission folder — with the file:line so the fix is one edit.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FOLDERS = {p.name for p in (ROOT / "algorithms").iterdir() if p.is_dir()}

# Documented placeholders, not slugs.
_PLACEHOLDERS = {"my-method"}

# Everything a person reads: top-level docs, the guides, the site, the CLI's own docstrings, each
# submission's build notes / readme / script comments, and the workflow-engine examples.
_DOC_FILES = (
    [ROOT / "README.md", ROOT / "CONTRACT.md"]
    + sorted((ROOT / "docs").rglob("*.md"))
    + sorted((ROOT / "web").glob("*.html"))
    + sorted((ROOT / "qsm_ci").glob("*.py"))
    + sorted(p for pat in ("BUILD.md", "README.md", "algorithm.yml", "*.py", "*.sh", "*.m")
             for p in (ROOT / "algorithms").glob(f"*/{pat}"))
    + sorted(p for p in (ROOT / "examples").rglob("*") if p.is_file())
)

_RUN = re.compile(r"qsm-ci run (\S+)")
_PATH = re.compile(r"algorithms/([A-Za-z0-9_-]+)")
_PIPELINE = re.compile(r"--pipeline ([A-Za-z0-9_,-]+)")


def _slug_refs(text: str):
    """(line_no, slug) for every slug-shaped reference in the text. Flags, paths, template
    variables and `<placeholder>`s are not slugs and are skipped."""
    for no, line in enumerate(text.splitlines(), 1):
        for m in _RUN.finditer(line):
            tok = m.group(1).rstrip("`'\")\\.,;:")
            if not tok or tok[0] in "-<&{$*.…" or "/" in tok or tok in _PLACEHOLDERS:
                continue
            yield no, tok
        for m in _PATH.finditer(line):
            yield no, m.group(1)
        for m in _PIPELINE.finditer(line):
            for tok in m.group(1).split(","):
                if tok:
                    yield no, tok


def test_docs_reference_only_existing_submissions():
    assert len(_DOC_FILES) > 100, "doc file set collapsed — the globs above no longer match the repo"
    bad = []
    for f in _DOC_FILES:
        for no, slug in _slug_refs(f.read_text(errors="replace")):
            if slug not in FOLDERS:
                bad.append(f"{f.relative_to(ROOT)}:{no}: {slug}")
    assert not bad, (
        "docs reference algorithm slugs/folders that don't exist under algorithms/ "
        "(renamed or removed?):\n  " + "\n  ".join(bad)
    )


def test_gitignore_algorithm_patterns_name_existing_folders():
    """Every `algorithms/<folder>/…` pattern in .gitignore must match a real folder — the
    "CI must pull, not build" Dockerfile patterns silently stopped matching after the renames
    (issue #220), which would have let a fresh Dockerfile get committed."""
    bad = []
    for no, line in enumerate((ROOT / ".gitignore").read_text().splitlines(), 1):
        line = line.strip()
        if not line.startswith("algorithms/"):
            continue
        folder = line.split("/")[1]
        if "*" in folder:
            continue  # a glob over every submission
        if folder not in FOLDERS:
            bad.append(f".gitignore:{no}: {line}")
    assert not bad, "gitignore patterns for folders that don't exist:\n  " + "\n  ".join(bad)
