#!/usr/bin/env python3
"""Recompute χ-separation metrics from stored source maps, without re-running any method.

A χ-sep run scored with `pipeline.py --emit-volumes` publishes its two source maps (volumes.recon =
χ+, volumes.recon-dia = χ−) to the Hugging Face volumes repo. When the χ-sep metric set changes, this
re-scores those maps against a local copy of the phantom, exactly as `pipeline._score_chisep` would
(the per-source set via qsm_eval.score_arrays, plus qsm_eval.chisep_joint_metrics), and replaces the
rows' para_*/dia_* and joint metrics in results/index.json. Everything else on a row is kept.

    # every χ-sep row of one phantom in the index (downloads the maps; --write to save)
    python scripts/rescore_chisep.py index --phantom meso-3t --dataset data/meso-3t [--write]

    # one pair of maps on disk -> JSON on stdout (for outputs that were never published)
    python scripts/rescore_chisep.py pair --dataset data/meso-3t chi-para.nii.gz chi-dia.nii.gz

`--dataset` is the unpacked phantom (groundtruth/chi-para, chi-dia, dseg, [wm_rois, theta];
inputs/mask). The score mask is inputs/mask.nii.gz, the full brain mask every run is scored on.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import urllib.request
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "eval"))
import qsm_eval as qe  # noqa: E402

# Keys an older scorer wrote that the current one no longer does (replaced by the *_excess terms,
# which measure the excess over the truth rather than the mean |recon|).
RETIRED_KEYS = ("para_calc_leak", "dia_iron_leak")


def _clean(v):
    if isinstance(v, float) and not math.isfinite(v):
        return None
    return v


def load_truth(dataset: Path) -> dict:
    g, i = dataset / "groundtruth", dataset / "inputs"
    opt = lambda p: qe.load(p) if p.exists() else None  # noqa: E731
    seg = opt(g / "dseg.nii.gz")
    return {"para": qe.load(g / "chi-para.nii.gz"), "dia": qe.load(g / "chi-dia.nii.gz"),
            "mask": (qe.load(i / "mask.nii.gz") > 0.5).astype(np.uint8),
            "seg": None if seg is None else np.rint(seg).astype(np.int32),
            "wm_rois": opt(g / "wm_rois.nii.gz"), "theta": opt(g / "theta.nii.gz")}


def score_pair(rec_para: np.ndarray, rec_dia: np.ndarray, t: dict) -> dict:
    """The metrics `pipeline._score_chisep` puts on a row (prefixed per source + joint)."""
    out = {}
    for comp, rec in (("para", rec_para), ("dia", rec_dia)):
        dia = comp == "dia"
        m, _ = qe.score_arrays(rec, t[comp], t["mask"], "chisep", seg=t["seg"], component=comp,
                               wm_rois=t["wm_rois"] if dia else None, theta=t["theta"] if dia else None)
        out.update({f"{comp}_{k}": _clean(v) for k, v in m.items()})
    jt = qe.chisep_joint_metrics(rec_para, rec_dia, t["para"], t["dia"], t["mask"], t["seg"])
    out.update({k: _clean(v) for k, v in jt.items()})
    return out


def _fetch(url: str, cache: Path) -> Path:
    dest = cache / url.split("/resolve/main/", 1)[-1]
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_suffix(dest.suffix + ".part")
        urllib.request.urlretrieve(url, tmp)
        tmp.rename(dest)
    return dest


def cmd_index(a) -> None:
    idx_path = Path(a.index)
    doc = json.loads(idx_path.read_text())
    t = load_truth(Path(a.dataset))
    n = 0
    for r in doc["runs"]:
        vols = r.get("volumes") or {}
        if (r.get("domain") != "chisep" or r.get("stage") != "chi-separation"
                or r.get("phantom") != a.phantom or r.get("status") != "ok"
                or not vols.get("recon") or not vols.get("recon-dia")):
            continue
        if a.inputs and (r.get("inputs") or "gt") != a.inputs:
            continue
        try:
            rp = qe.load(_fetch(vols["recon"], Path(a.cache)))
            rd = qe.load(_fetch(vols["recon-dia"], Path(a.cache)))
        except Exception as e:  # noqa: BLE001 — a missing volume skips that row, never the batch
            print(f"  skip {r['id']}: {e}", file=sys.stderr)
            continue
        if rp.shape != t["mask"].shape or rd.shape != t["mask"].shape:
            print(f"  skip {r['id']}: shape {rp.shape} != phantom {t['mask'].shape}", file=sys.stderr)
            continue
        new = score_pair(rp, rd, t)
        for k in RETIRED_KEYS:
            r["metrics"].pop(k, None)
        r["metrics"].update(new)
        n += 1
        print(f"  {r['id']:<40} split_rms_rw={new.get('split_rms_rw')} total_rms_rw={new.get('total_rms_rw')}")
    print(f"rescored {n} rows on {a.phantom}")
    if a.write:
        idx_path.write_text(json.dumps(doc, indent=2) + "\n")
        print(f"wrote {idx_path}")


def cmd_pair(a) -> None:
    t = load_truth(Path(a.dataset))
    print(json.dumps(score_pair(qe.load(a.para), qe.load(a.dia), t), indent=2))


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    pi = sub.add_parser("index", help="rescore every χ-sep row of a phantom in index.json")
    pi.add_argument("--phantom", required=True)
    pi.add_argument("--dataset", required=True, help="unpacked phantom dir (groundtruth/, inputs/)")
    pi.add_argument("--index", default=str(ROOT / "results" / "index.json"))
    pi.add_argument("--inputs", choices=["gt", "l3"], default=None, help="only rows of this input level")
    pi.add_argument("--cache", default=str(Path.home() / ".cache" / "qsm-ci" / "rescore-volumes"))
    pi.add_argument("--write", action="store_true", help="save the updated index (default: dry run)")
    pp = sub.add_parser("pair", help="score one χ+/χ− pair on disk, print JSON")
    pp.add_argument("--dataset", required=True)
    pp.add_argument("para", type=Path)
    pp.add_argument("dia", type=Path)
    a = p.parse_args()
    {"index": cmd_index, "pair": cmd_pair}[a.cmd](a)


if __name__ == "__main__":
    main()
