"""score.yml's merge job runs `git add results/index.json results/scoring-state.json` under
`set -e`. If scoring-state.json is gitignored, git add exits 1 on it, the whole step dies BEFORE the
commit, and a rescore's freshly published volume URLs never reach main (the 2026-09-11 merge that
sharded 326 runs' volumes on the Hub, pruned their flat copies, then failed exactly here — leaving
every one of those rows pointing at a 404). /results/* is ignored wholesale; each file the workflow
commits needs its own `!` exception."""
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COMMITTED_BY_WORKFLOWS = ("results/index.json", "results/scoring-state.json",
                          "results/repro.json", "results/repro_regions.json")


def test_files_the_workflows_commit_are_not_gitignored():
    for rel in COMMITTED_BY_WORKFLOWS:
        r = subprocess.run(["git", "check-ignore", "-q", rel], cwd=ROOT)
        assert r.returncode == 1, f"{rel} is gitignored; score.yml/repro.yml `git add` it and would exit 1"
