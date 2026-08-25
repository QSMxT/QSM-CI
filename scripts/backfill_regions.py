#!/usr/bin/env python3
"""Backfill per-run results/<id>/regions.json for already-scored runs from their archived volumes.

Per-region descriptive stats (region_summary in eval/qsm_eval.py) normally ride out of the scorer
during a rescore, so runs scored BEFORE the feature existed have no per-run regions file until their
next rescore. But their scored recon volumes are already archived — results/<id>/recon.nii.gz
locally, or the Hugging Face volumes repo recorded in each run's `volumes.recon` URL — so the stats
can be reproduced exactly without re-running any algorithm: recon from the archive, truth/dseg/mask
from the phantom's local dataset, and the same valid-support score mask the pipeline uses
(base mask ∧ |recon| > 0, see pipeline._valid_mask).

Writes one results/<id>/regions.json per run (the same per-run artifact pipeline.write_run_regions
emits). Those files serve the local dev site directly (results/<id>/regions.json fallback) and are
uploaded to Hugging Face + recorded as `regions_url` by scripts/publish_volumes.py — after backfilling,
run `HF_TOKEN=… HF_VOLUMES_REPO=… python scripts/publish_volumes.py results` to publish them.

Usage: backfill_regions.py [--filter SUBSTR] [--composed] [--limit N]
  Default scope: sim-track isolated dipole runs (what the leaderboard's Regions figures compare).
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

import nibabel as nib
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "eval"))
from qsm_eval import region_summary  # noqa: E402

CACHE = ROOT / ".work" / "regions_cache"


def default_phantom(reg: dict, track: str) -> str | None:
    for key, v in reg.items():
        if v.get("track") == track and v.get("default"):
            return key
    return None


def fetch_recon(r: dict) -> "tuple[Path, bool] | None":
    """(recon path, is_temp). is_temp=True marks a freshly-downloaded volume the caller should
    delete after use — streaming keeps peak disk at ~one volume (~5 MB) instead of accumulating the
    whole archive (~4 GB over the composed set), which fills this near-full box."""
    local = ROOT / "results" / r["id"] / "recon.nii.gz"
    if local.exists():
        return local, False
    url = (r.get("volumes") or {}).get("recon")
    if not url:
        return None
    CACHE.mkdir(parents=True, exist_ok=True)
    dst = CACHE / f"{r['id']}__recon.nii.gz"
    print(f"  fetching {url.split('/')[-1]}")
    urllib.request.urlretrieve(url, dst)
    return dst, True


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--filter", default=None, help="only run ids containing this substring")
    ap.add_argument("--composed", action="store_true",
                    help="include composed sim runs too (many volumes — slow, big download)")
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    reg = json.loads((ROOT / "scripts" / "datasets.json").read_text())
    runs = json.loads((ROOT / "results" / "index.json").read_text())["runs"]

    def eligible(r):
        if r.get("track") != "sim" or r.get("status") != "ok" or r.get("domain") == "chisep":
            return False  # chisep needs the dia volume set, which the archive doesn't carry yet
        if r.get("mode") == "isolated" and r.get("stage") != "dipole":
            return False  # isolated field/BFR runs score a field map — no region χ stats
        if r.get("mode") == "composed" and not args.composed:
            return False
        return not args.filter or args.filter in r["id"]

    todo = [r for r in runs if eligible(r)][: args.limit]
    print(f"backfilling {len(todo)} run(s)")

    cache = {}  # phantom -> (truth, seg, base_mask)
    done = 0
    for r in todo:
        phantom = r.get("phantom") or default_phantom(reg, "sim")
        if phantom not in reg:
            print(f"  !! {r['id']}: unknown phantom {phantom}"); continue
        if phantom not in cache:
            ds = ROOT / reg[phantom]["path"]
            truth_p, seg_p, mask_p = (ds / "groundtruth/chimap.nii.gz", ds / "groundtruth/dseg.nii.gz",
                                      ds / "inputs/mask.nii.gz")
            if not (truth_p.exists() and seg_p.exists() and mask_p.exists()):
                cache[phantom] = None
            else:
                cache[phantom] = (
                    np.asarray(nib.load(str(truth_p)).get_fdata(dtype=np.float64)),
                    np.rint(nib.load(str(seg_p)).get_fdata()).astype(np.int32),
                    nib.load(str(mask_p)).get_fdata() > 0.5,
                )
        if cache[phantom] is None:
            print(f"  !! {r['id']}: phantom {phantom} lacks local truth/dseg/mask"); continue
        truth, seg, base = cache[phantom]
        fetched = fetch_recon(r)
        if fetched is None:
            print(f"  !! {r['id']}: no archived recon volume"); continue
        recon_p, is_temp = fetched
        try:
            recon = np.asarray(nib.load(str(recon_p)).get_fdata(dtype=np.float64))
        finally:
            if is_temp:   # stream: drop the download now that it's in memory (near-full disk)
                recon_p.unlink(missing_ok=True)
        if recon.shape != truth.shape:
            print(f"  !! {r['id']}: shape mismatch {recon.shape} vs {truth.shape}"); continue
        valid = (np.abs(recon) > 0) & base
        if not valid.any():
            valid = base
        entry = {"chi": region_summary(recon, truth, seg, valid)}
        d = ROOT / "results" / r["id"]
        d.mkdir(parents=True, exist_ok=True)
        (d / "regions.json").write_text(json.dumps(entry, indent=2) + "\n")
        done += 1
        print(f"  {r['id']}: {len(entry['chi']['recon'])} regions")

    print(f"wrote {done} per-run results/<id>/regions.json file(s); "
          f"publish with scripts/publish_volumes.py to set regions_url")


if __name__ == "__main__":
    main()
