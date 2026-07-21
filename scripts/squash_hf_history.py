#!/usr/bin/env python3
"""Squash the viewer-volumes dataset repo's git history to a single commit.

`publish_volumes.py` overwrites each run's `{recon,truth,error}.nii.gz` in place. On the Hugging
Face Hub (git + LFS), overwriting a *changed* volume keeps the old LFS object in history — so a full
re-publish that regenerates many volumes (e.g. after changing how the error map is computed) leaves
gigabytes of orphaned old versions counting against the account's storage quota. Collapsing the
history to a single commit reclaims those old LFS versions.

Run this after a FULL re-publish only (score.yml passes it on full rescores; focused re-publishes
churn too few files to be worth squashing). It is destructive — history and old LFS versions are
permanently removed — which is fine here: the volumes are regenerable and nothing needs old
revisions. The reclaimed quota is reflected on the Hub within ~36h, not immediately.

Best-effort: any failure is logged and ignored, so storage housekeeping never fails the scoring run.

Env:
  HF_TOKEN         Hugging Face token with write access to the dataset repo
  HF_VOLUMES_REPO  dataset repo id, e.g. "qsmxt/qsm-ci-volumes"
"""
from __future__ import annotations

import os
import sys


def main() -> int:
    repo = os.environ.get("HF_VOLUMES_REPO")
    token = os.environ.get("HF_TOKEN")
    if not repo or not token:
        print("HF_VOLUMES_REPO / HF_TOKEN not set — skipping history squash")
        return 0
    try:
        from huggingface_hub import HfApi

        HfApi(token=token).super_squash_history(
            repo_id=repo,
            repo_type="dataset",
            branch="main",
            commit_message="squash volume history to reclaim old LFS versions",
        )
        print(f"squashed {repo} history — orphaned old LFS versions reclaimed within ~36h")
    except Exception as exc:  # noqa: BLE001 — never fail the workflow over storage housekeeping
        print(f"! history squash failed (non-fatal): {exc}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
