#!/usr/bin/env bash
# Post (or update) a metrics summary comment on the PR, with slice figures.
# Modeled on the QSM.rs integration-test PR comment. Requires `gh` and GITHUB_TOKEN.
#
# Usage: pr_comment.sh <slug> <track> <figures-dir>
set -euo pipefail

SLUG="${1:?}"; TRACK="${2:?}"; FIGDIR="${3:?}"
METRICS="${FIGDIR}/metrics.json"

if [ -f "$METRICS" ]; then
  body=$(jq -r --arg slug "$SLUG" --arg track "$TRACK" '
    "### QSM-CI · \($slug) · track `\($track)`\n\n" +
    "| metric | value |\n|---|---|\n" +
    (.metrics | to_entries | map("| \(.key) | \(.value) |") | join("\n"))
  ' "$METRICS")
else
  body="### QSM-CI · ${SLUG} · track \`${TRACK}\`\n\n**DNF** — the algorithm did not produce a valid \`chimap.nii.gz\`."
fi

# TODO: upload figures (FIGDIR/*.png) and embed them; gh does not host images directly.
printf '%b\n' "$body" | gh pr comment "${PR_NUMBER:-}" --body-file - || \
  printf '%b\n' "$body"   # fall back to logging if not in a PR context
