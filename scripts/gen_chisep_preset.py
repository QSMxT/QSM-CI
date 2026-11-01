#!/usr/bin/env python3
"""Regenerate a χ-separation dataset from its qsm-forward preset, then pack it for QSM-CI.

The phantom itself is qsm-forward's (`qsm_forward.chisep` presets); QSM-CI holds no generation logic
for these datasets. This script only:

  1. reads the dataset's `generator` block from scripts/datasets.json
     (`{"tool": "qsm-forward", "ref": <commit>, "preset": <name>, ...}`),
  2. refuses to run unless the installed qsm-forward is that pinned commit (pip records it in
     direct_url.json when installed from git; --allow-unpinned skips the check, for development),
  3. calls `qsm_forward.chisep.generate_chisep_bids` with the preset (and its `r2prime_source` and
     `degrade_levels` overrides, if the entry sets them: `degrade_levels: ["L3"]` also writes
     qsm-forward's controlled-degradation inputs, which pack_dataset.py ships as inputs-l3/),
  4. packs the BIDS tree with pack_dataset.py and masks the derived maps and ground truth to the
     brain (gen_chisep.mask_derived_to_brain), as every χ-separation zip is packed,
  5. with --zip, writes <out>.zip (inputs/ + groundtruth/, and any inputs-<level>/, at the root,
     `prepacked: true`) and prints its size and md5 for the OSF upload.

Install the pinned generator first, e.g.
  pip install "qsm-forward @ git+https://github.com/astewartau/qsm-forward@<ref>"
The mesoscopic presets read their signal look-up tables from $QSM_FORWARD_MESO_LUT_DIR
(see qsm-forward's README); the head model is the Challenge 2.0 data directory (--qsmf-data).

Usage:
  python scripts/gen_chisep_preset.py meso-3t --qsmf-data <head-model dir> \
      --wm-rois-src <WM_fibers_seg.nii.gz> --out data/meso-3t/scoring [--zip]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
QSM_FORWARD_REPO = "https://github.com/astewartau/qsm-forward"


def generator(phantom: str, registry: Path = HERE / "datasets.json") -> dict:
    """The registry entry's generator block, validated."""
    reg = json.loads(registry.read_text())
    if phantom not in reg:
        raise SystemExit(f"unknown phantom '{phantom}' — add it to scripts/datasets.json")
    g = reg[phantom].get("generator")
    if not g:
        raise SystemExit(f"'{phantom}' has no generator block: it is not built from a qsm-forward preset")
    if g.get("tool") != "qsm-forward" or not g.get("ref") or not g.get("preset"):
        raise SystemExit(f"'{phantom}': generator needs tool=qsm-forward, a pinned ref and a preset")
    return g


def installed_ref() -> "str | None":
    """The git commit the installed qsm-forward was built from (pip's direct_url.json), if any."""
    from importlib import metadata
    try:
        raw = metadata.distribution("qsm-forward").read_text("direct_url.json")
    except metadata.PackageNotFoundError:
        return None
    if not raw:
        return None
    return (json.loads(raw).get("vcs_info") or {}).get("commit_id")


def check_pin(ref: str, allow_unpinned: bool = False) -> None:
    got = installed_ref()
    if got and got.startswith(ref):
        return
    msg = (f"installed qsm-forward is {got or 'not a git install'}, the registry pins {ref}: "
           f'pip install "qsm-forward @ git+{QSM_FORWARD_REPO}@{ref}"')
    if not allow_unpinned:
        raise SystemExit(msg)
    print(f"WARNING: {msg} (continuing: --allow-unpinned)", file=sys.stderr)


def preset_overrides(g: dict) -> dict:
    """ChisepConfig overrides the registry entry asks for on top of the named preset."""
    out = {k: g[k] for k in ("r2prime_source",) if k in g}
    if g.get("degrade_levels"):
        out["degrade_levels"] = tuple(g["degrade_levels"])
    return out


def generate(g: dict, qsmf_data: Path, bids: Path, wm_rois: "Path | None") -> None:
    from qsm_forward import chisep
    cfg = chisep.preset(g["preset"], **preset_overrides(g))
    if g.get("wm_rois") and wm_rois is None:
        raise SystemExit("this dataset ships groundtruth/wm_rois.nii.gz: pass --wm-rois-src "
                         "(Ridani et al.'s Masks/WM_fibers_seg.nii.gz, OSF 9xwhz)")
    chisep.generate_chisep_bids(str(qsmf_data), str(bids), cfg,
                                wm_rois=str(wm_rois) if wm_rois else None)


def pack(bids: Path, out: Path, ridani: bool) -> None:
    subprocess.run([sys.executable, str(HERE / "pack_dataset.py"), str(bids), str(out), "--chisep"],
                   check=True)
    sys.path.insert(0, str(HERE))
    from gen_chisep import mask_derived_to_brain
    mask_derived_to_brain(out)
    if ridani:
        # The Ridani family ships the tissue segmentation as an input too (as the earlier zips do).
        shutil.copy(out / "groundtruth" / "dseg.nii.gz", out / "inputs" / "dseg.nii.gz")


def make_zip(out: Path) -> Path:
    z = out.with_suffix(".zip") if out.suffix else Path(str(out) + ".zip")
    if z.exists():
        z.unlink()
    dirs = ["inputs", "groundtruth"] + sorted(p.name for p in out.glob("inputs-*") if p.is_dir())
    subprocess.run(["zip", "-qr", "-X", str(z), *dirs], cwd=out, check=True)
    md5 = hashlib.md5(z.read_bytes()).hexdigest()
    print(f"{z}  {z.stat().st_size} bytes  md5 {md5}")
    return z


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("phantom", help="scripts/datasets.json key with a generator block")
    ap.add_argument("--qsmf-data", type=Path, required=True, help="Challenge 2.0 head-model data dir")
    ap.add_argument("--wm-rois-src", type=Path, default=None,
                    help="Ridani et al.'s WM fibre-bundle atlas (OSF 9xwhz Masks/WM_fibers_seg.nii.gz)")
    ap.add_argument("--out", type=Path, required=True, help="packed dataset dir (inputs/ + groundtruth/)")
    ap.add_argument("--bids", type=Path, default=None, help="keep the qsm-forward BIDS tree here")
    ap.add_argument("--zip", action="store_true", help="also write <out>.zip and print size + md5")
    ap.add_argument("--allow-unpinned", action="store_true",
                    help="run with a qsm-forward other than the pinned commit (development only)")
    a = ap.parse_args(argv)
    g = generator(a.phantom)
    check_pin(g["ref"], a.allow_unpinned)
    bids = a.bids or Path(tempfile.mkdtemp(prefix=f"{a.phantom}-bids-"))
    if bids.exists() and any(bids.iterdir()):
        raise SystemExit(f"{bids} is not empty")
    if a.out.exists():
        shutil.rmtree(a.out)
    generate(g, a.qsmf_data, bids, a.wm_rois_src)
    pack(bids, a.out, ridani=g["preset"].startswith("ridani-"))
    if a.bids is None:
        shutil.rmtree(bids)
    if a.zip:
        make_zip(a.out)


if __name__ == "__main__":
    main()
