#!/usr/bin/env bash
# Post (or update) a metrics comment on the PR for a submission's isolated run.
# Reads the run pipeline.py wrote into results/index.json. Requires `gh` + GH_TOKEN.
#
# Usage: pr_comment.sh <slug>
set -euo pipefail

SLUG="${1:?slug required}"

body=$(python3 - "$SLUG" <<'PY'
import json, sys, pathlib
slug = sys.argv[1]
idx = json.loads(pathlib.Path("results/index.json").read_text())
runs = [r for r in idx.get("runs", []) if r.get("slug") == slug and r.get("mode") == "isolated"]
if not runs:
    print(f"### QSM-CI · {slug}\n\n**DNF** — no valid output was produced.")
    raise SystemExit
r = runs[0]
lines = [f"### QSM-CI · `{slug}` · stage `{r.get('stage')}` · isolated",
         f"Scored artifact: `{r.get('artifact')}` ({r.get('kind')}), runtime {r.get('runtime_s'):.1f}s\n",
         "| metric | value |", "|---|---|"]
for k, v in (r.get("metrics") or {}).items():
    lines.append(f"| {k} | {'—' if v is None else round(v, 4)} |")
lines.append("\n_Composed BFR×inversion results appear on the [leaderboard](https://astewartau.github.io/qsm-ci/)._")
print("\n".join(lines))
PY
)

printf '%s\n' "$body" | gh pr comment "${PR_NUMBER:-}" --body-file - || printf '%s\n' "$body"
