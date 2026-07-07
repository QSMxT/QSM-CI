#!/usr/bin/env bash
# Publish the dev phantom (data/sim/dev) as a public GitHub release asset, so that
# `qsm-ci test` / `qsm-ci fetch` can download it (see qsm_ci/data.py DEFAULT_URL).
#
# The dev phantom is small and openly releasable (both inputs/ AND groundtruth/) — it is NOT the
# held-out scoring set. Regenerate it first if needed (see data/sim/README.md). Requires `gh` with
# push access.
#
# Usage:  scripts/publish_dev_phantom.sh [owner/repo]
set -euo pipefail

REPO="${1:-astewartau/qsm-ci}"
TAG="dev-phantom"
ASSET="qsm-ci-dev-phantom.tar.gz"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEV="$ROOT/data/sim/dev"

[ -f "$DEV/inputs/mask.nii.gz" ] || { echo "no dev phantom at $DEV — regenerate it (data/sim/README.md)"; exit 1; }
[ -d "$DEV/groundtruth" ] || { echo "no groundtruth/ at $DEV"; exit 1; }

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
tar -C "$DEV" -czf "$tmp/$ASSET" inputs groundtruth
echo "packed $(du -h "$tmp/$ASSET" | cut -f1) -> $ASSET"

if gh release view "$TAG" --repo "$REPO" >/dev/null 2>&1; then
  gh release upload "$TAG" "$tmp/$ASSET" --repo "$REPO" --clobber
else
  gh release create "$TAG" "$tmp/$ASSET" --repo "$REPO" \
    --title "QSM-CI dev phantom" \
    --notes "Small open phantom (inputs + ground truth) for local \`qsm-ci test\`. Not the scoring set."
fi
echo "published: https://github.com/$REPO/releases/download/$TAG/$ASSET"
