#!/usr/bin/env python3
"""Reproducibility evaluation for the no-ground-truth harmonization track.

The `repro` track reconstructs the SAME subject from many acquisitions (scanner x protocol x run).
There is no truth map; the question is how reproducible each pipeline's χ values are across
acquisitions — the analysis Marta Lancione ran with two pipelines (per-ROI orthogonal ax+b fits,
Bland-Altman agreement), generalized over the whole QSM-CI combination matrix.

Stages (subcommands), all idempotent:

  register   Rigid-register every acquisition's first-echo magnitude to the TARGET acquisition's
             (default cima-bridge-run1). Transforms land in data/harmonization/_align/<acq>.tfm.
             Needs SimpleITK.
  seg        SynthSeg the target's first-echo magnitude -> _align/dseg.nii.gz (docker), or install
             an externally produced segmentation via --seg. One segmentation defines the ROIs for
             every comparison (per Marta's method), so ROI definitions can't drift between runs.
  stats      For every collected repro run (results/index.json + results/<id>/recon.nii.gz):
             resample its χ map into target space, reference it to the whole-brain mean, and record
             per-ROI means -> results/repro_rois.json. ROIs with <90% valid coverage are dropped
             (brain coverage differs between acquisitions).
  fits       Pairwise comparisons per pipeline -> results/repro.json (the web payload):
               test-retest      same scanner+protocol, run i vs run j
               inter-scanner    same protocol+run, prisma vs cima
               inter-protocol   same scanner+run, protocol vs bridge
             Each pair: orthogonal (total-least-squares) slope a + intercept b — |a-1| is the
             headline —, Pearson r, Bland-Altman bias and limits of agreement.

Typical use (after pipeline runs have collected recons):
  python scripts/repro_eval.py register
  python scripts/repro_eval.py seg          # or --seg path/to/dseg.nii.gz
  python scripts/repro_eval.py stats
  python scripts/repro_eval.py fits
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import nibabel as nib
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
ALIGN = ROOT / "data" / "harmonization" / "_align"
RESULTS = ROOT / "results"
DEFAULT_TARGET = "cima-bridge-run1"

# SynthSeg labels kept for ROI statistics (cortical/subcortical GM, WM, brainstem, cerebellum —
# ventricles/CSF excluded). WM ROIs stay in per Marta's finding that they don't behave differently.
ROI_LABELS = {
    2: "Left-Cerebral-WM", 3: "Left-Cerebral-Cortex", 7: "Left-Cerebellum-WM",
    8: "Left-Cerebellum-Cortex", 10: "Left-Thalamus", 11: "Left-Caudate", 12: "Left-Putamen",
    13: "Left-Pallidum", 16: "Brain-Stem", 17: "Left-Hippocampus", 18: "Left-Amygdala",
    26: "Left-Accumbens", 28: "Left-VentralDC", 41: "Right-Cerebral-WM",
    42: "Right-Cerebral-Cortex", 46: "Right-Cerebellum-WM", 47: "Right-Cerebellum-Cortex",
    49: "Right-Thalamus", 50: "Right-Caudate", 51: "Right-Putamen", 52: "Right-Pallidum",
    53: "Right-Hippocampus", 54: "Right-Amygdala", 58: "Right-Accumbens", 60: "Right-VentralDC",
}
MIN_ROI_COVERAGE = 0.90
MIN_PAIR_ROIS = 8  # a fit over fewer common ROIs than this is too fragile to report
SLOPE_DEV_CAP = 2.0  # |a-1| beyond this is a degenerate/failed fit, not a reproducibility value


def repro_acquisitions() -> dict[str, dict]:
    """The repro-track phantom registry entries: id -> {scanner, protocol, run, path}."""
    reg = json.loads((ROOT / "scripts" / "datasets.json").read_text())
    out = {}
    for key, v in reg.items():
        if v.get("track") != "repro":
            continue
        m = re.match(r"(prisma|cima)-(.+)-(run\d)$", key)
        if not m:
            continue
        out[key] = {"scanner": m.group(1), "protocol": m.group(2), "run": m.group(3),
                    "path": ROOT / v["path"]}
    return out


def first_echo_magnitude(acq_path: Path) -> "nib.Nifti1Image":
    img = nib.load(str(acq_path / "inputs" / "magnitude.nii.gz"))
    return nib.Nifti1Image(np.asanyarray(img.dataobj)[..., 0].astype(np.float32), img.affine)


# ---------------------------------------------------------------------------------------------------
# register
# ---------------------------------------------------------------------------------------------------

def _register_one(key, moving_path, fixed, tfm_path, is_target, sitk) -> str:
    """Rigid-register one acquisition's first-echo magnitude to `fixed` (the target); write the
    transform to tfm_path. The target itself gets the identity. Shared by the whole-index `register`
    command and the per-job `stats --runs` path (which registers just its own acquisition)."""
    if is_target:
        sitk.WriteTransform(sitk.Euler3DTransform(), str(tfm_path))
        return "identity (target)"
    mov_nii = tfm_path.parent / f"_mov_{key}.nii.gz"
    nib.save(first_echo_magnitude(moving_path), str(mov_nii))
    moving = sitk.ReadImage(str(mov_nii), sitk.sitkFloat32)
    init = sitk.CenteredTransformInitializer(
        fixed, moving, sitk.Euler3DTransform(),
        sitk.CenteredTransformInitializerFilter.GEOMETRY)
    reg = sitk.ImageRegistrationMethod()
    # Mattes MI: robust to the contrast differences between protocols (GRE vs EPI, different TEs)
    reg.SetMetricAsMattesMutualInformation(numberOfHistogramBins=64)
    reg.SetMetricSamplingStrategy(reg.RANDOM)
    reg.SetMetricSamplingPercentage(0.2, seed=42)
    reg.SetInterpolator(sitk.sitkLinear)
    reg.SetOptimizerAsRegularStepGradientDescent(
        learningRate=1.0, minStep=1e-4, numberOfIterations=300,
        relaxationFactor=0.6, gradientMagnitudeTolerance=1e-6)
    reg.SetOptimizerScalesFromPhysicalShift()
    reg.SetShrinkFactorsPerLevel([4, 2, 1])
    reg.SetSmoothingSigmasPerLevel([2, 1, 0])
    reg.SmoothingSigmasAreSpecifiedInPhysicalUnitsOn()
    reg.SetInitialTransform(init, inPlace=False)
    tfm = reg.Execute(fixed, moving)
    sitk.WriteTransform(tfm, str(tfm_path))
    mov_nii.unlink()
    return f"metric={reg.GetMetricValue():.4f} ({reg.GetOptimizerIteration()} iters)"


def cmd_register(args) -> None:
    import SimpleITK as sitk  # deferred: only this stage needs it

    acqs = repro_acquisitions()
    if args.target not in acqs:
        raise SystemExit(f"unknown target '{args.target}'")
    ALIGN.mkdir(parents=True, exist_ok=True)
    (ALIGN / "target.json").write_text(json.dumps({"target": args.target}) + "\n")

    tgt_nii = ALIGN / "target_mag_e1.nii.gz"
    nib.save(first_echo_magnitude(acqs[args.target]["path"]), str(tgt_nii))
    fixed = sitk.ReadImage(str(tgt_nii), sitk.sitkFloat32)

    # Prep-only: just the target grid (+ its identity transform) so a one-time `prep` job can build
    # the reference frame (target_mag_e1 + dseg via seg) without fetching all 23 acquisitions — the
    # per-job `stats --runs` path registers each acquisition to this target itself.
    if getattr(args, "target_only", False):
        sitk.WriteTransform(sitk.Euler3DTransform(), str(ALIGN / f"{args.target}.tfm"))
        print(f"  {args.target}: target grid written (target-only)")
        return

    for key, acq in sorted(acqs.items()):
        tfm_path = ALIGN / f"{key}.tfm"
        if tfm_path.exists() and not args.force:
            continue
        print(f"  {key}: {_register_one(key, acq['path'], fixed, tfm_path, key == args.target, sitk)}")


# ---------------------------------------------------------------------------------------------------
# seg
# ---------------------------------------------------------------------------------------------------

def cmd_seg(args) -> None:
    dseg = ALIGN / "dseg.nii.gz"
    if args.seg:  # externally produced segmentation of the TARGET first-echo magnitude
        src = nib.load(str(args.seg))
        nib.save(nib.Nifti1Image(np.asanyarray(src.dataobj).astype(np.int16), src.affine), str(dseg))
        print(f"installed {args.seg} -> {dseg}")
        return
    if dseg.exists() and not args.force:
        print(f"{dseg} exists (use --force to redo)")
        return
    # mri_synthseg (robust, contrast-agnostic) on the target magnitude, via the official FreeSurfer
    # image — mri_synthseg is one of the license-free tools, and it emits standard FreeSurfer aseg
    # labels (the ids in ROI_LABELS). Runs on any GRE/EPI contrast, which is why it fits here.
    subprocess.run(
        ["docker", "run", "--rm", "--user", f"{os.getuid()}:{os.getgid()}",
         "-v", f"{ALIGN}:/data", args.image,
         "mri_synthseg", "--i", "/data/target_mag_e1.nii.gz", "--o", "/data/dseg_synthseg.nii.gz",
         "--robust", "--threads", "4"],
        check=True)
    # SynthSeg resamples to its own 1mm grid; bring labels back onto the target grid.
    import SimpleITK as sitk
    fixed = sitk.ReadImage(str(ALIGN / "target_mag_e1.nii.gz"))
    seg = sitk.ReadImage(str(ALIGN / "dseg_synthseg.nii.gz"))
    res = sitk.Resample(seg, fixed, sitk.Transform(), sitk.sitkNearestNeighbor, 0)
    sitk.WriteImage(res, str(dseg))
    print(f"wrote {dseg}")


# ---------------------------------------------------------------------------------------------------
# stats
# ---------------------------------------------------------------------------------------------------

def pipeline_identity(r: dict) -> str:
    """A UNIQUE '+'-joined pipeline id for a collected run — the thing reproducibility groups by.

    A full field-mapping+bfr+dipole run already carries the joined combo as its slug
    (`romeo-qsmrs+vsharp-qsmrs+rts-qsmrs`), which is unique. But a bfr+dipole / end-to-end SPAN
    keeps its bare method slug (`nextqsm`) while composing with EVERY field-mapping source, so slug
    alone collapses `romeo→nextqsm` and `laplacian→nextqsm` into one — distinct pipelines. Prepend
    the combo's field-mapping so each (field-map, span) is its own pipeline. The '+' join keeps the
    web's `reproName` (split on '+', name each stage) working unchanged."""
    combo = r.get("combo") or {}
    if combo.get("bfr") and combo.get("dipole"):
        return r["slug"]                       # full fm+bfr+dipole — slug is already the joined combo
    fm = combo.get("field_mapping")
    if fm and fm != "gt":                       # a span composed with a field-mapping method
        return f"{fm}+{r['slug']}"
    return r["slug"]                            # end-to-end span (its own field-mapping) or single method


def _collected_runs() -> list[dict]:
    idx = json.loads((RESULTS / "index.json").read_text()) if (RESULTS / "index.json").exists() else {}
    rows = idx.get("runs", idx) if isinstance(idx, dict) else idx
    return [r for r in rows if isinstance(r, dict) and r.get("track") == "repro"
            and r.get("status") == "ok" and r.get("phantom")
            and (RESULTS / r["id"] / "recon.nii.gz").exists()]


def _roi_row(rid, acq, fixed, dseg, roi_masks, tfm, sitk) -> "dict | None":
    """Per-ROI ref-subtracted χ means (+ n/mean/std/median) for one run's recon, resampled into
    target space with `tfm`. Returns the row dict, or None if the recon is missing or barely overlaps
    the segmentation. The single per-recon computation shared by whole-index and per-job stats."""
    recon_p = RESULTS / rid / "recon.nii.gz"
    if not recon_p.exists():
        return None
    recon = sitk.ReadImage(str(recon_p), sitk.sitkFloat32)
    chi = sitk.GetArrayFromImage(sitk.Resample(recon, fixed, tfm, sitk.sitkLinear, 0.0))
    valid = np.isfinite(chi) & (np.abs(chi) > 0)   # the recon's own support = its valid region
    brain = valid & (dseg > 0)
    if brain.sum() < 1000:
        return None
    ref = float(chi[brain].mean())                 # whole-brain reference (per Marta's analysis)
    roi_means, roi_stats = {}, {}
    for lab, m in roi_masks.items():
        cov = valid[m].mean()
        if cov < MIN_ROI_COVERAGE:
            continue                                # slab coverage differs between acquisitions
        v = chi[m & valid] - ref                    # ref-subtracted, same convention as the fits
        roi_means[str(lab)] = round(float(v.mean()), 6)
        roi_stats[str(lab)] = {"n": int(v.size), "mean": round(float(v.mean()), 6),
                               "std": round(float(v.std()), 6),
                               "median": round(float(np.median(v)), 6)}
    return {"acq": acq, "ref_mean": round(ref, 6), "rois": roi_means, "roi_stats": roi_stats}


def _stats_setup(sitk):
    """Load the shared target grid + segmentation + ROI masks (target.json / target_mag_e1 / dseg)."""
    target = json.loads((ALIGN / "target.json").read_text())["target"]
    fixed = sitk.ReadImage(str(ALIGN / "target_mag_e1.nii.gz"), sitk.sitkFloat32)
    dseg = np.rint(sitk.GetArrayFromImage(sitk.ReadImage(str(ALIGN / "dseg.nii.gz")))).astype(int)
    roi_masks = {lab: dseg == lab for lab in ROI_LABELS if (dseg == lab).sum() >= 50}
    return target, fixed, dseg, roi_masks


def cmd_stats(args) -> None:
    import SimpleITK as sitk

    target, fixed, dseg, roi_masks = _stats_setup(sitk)
    acqs = repro_acquisitions()

    # Per-job (CI-scale) path: compute ROI means for just the runs in a pipeline.py --runs-out file
    # and write them BACK into that file, registering this file's acquisition(s) on the fly. Each
    # score job does this on its own recons, so the evaluate job never needs the volumes — only the
    # tiny runs-JSON with `rois` travels onward. The target grid + dseg come from a one-time prep.
    if getattr(args, "runs", None):
        rows = json.loads(Path(args.runs).read_text())
        tcache = {}
        n = 0
        for r in rows:
            acq = r.get("phantom")
            if r.get("track") != "repro" or r.get("status") != "ok" or acq not in acqs:
                continue
            if acq not in tcache:                  # register this acquisition to the target once
                tfm_path = ALIGN / f"{acq}.tfm"
                if not tfm_path.exists():
                    _register_one(acq, acqs[acq]["path"], fixed, tfm_path, acq == target, sitk)
                tcache[acq] = sitk.ReadTransform(str(tfm_path))
            row = _roi_row(r["id"], acq, fixed, dseg, roi_masks, tcache[acq], sitk)
            if row:
                r["pipeline"] = pipeline_identity(r)
                r["ref_mean"], r["rois"], r["roi_stats"] = row["ref_mean"], row["rois"], row["roi_stats"]
                n += 1
        Path(args.runs).write_text(json.dumps(rows, indent=2) + "\n")
        print(f"per-job stats: {n} runs -> {args.runs}")
        return

    # Whole-index (Bunya) path: every collected run -> results/repro_rois.json.
    rows = {}
    for r in _collected_runs():
        acq = r["phantom"]
        if acq not in acqs:
            continue
        tfm_path = ALIGN / f"{acq}.tfm"
        if not tfm_path.exists():
            print(f"  !! no transform for {acq} — run `register` first"); continue
        row = _roi_row(r["id"], acq, fixed, dseg, roi_masks, sitk.ReadTransform(str(tfm_path)), sitk)
        if row is None:
            print(f"  !! {r['id']}: no usable recon/overlap"); continue
        rows[r["id"]] = {"pipeline": pipeline_identity(r), **row}
        print(f"  {r['id']}: {len(row['rois'])} ROIs")
    # Refuse to overwrite a real payload with an empty one. This command needs the harmonization
    # recons (results/<id>/recon.nii.gz) and the registration products under data/harmonization/_align,
    # which live on the HPC side — off it, `_collected_runs()` matches nothing and writing the result
    # would silently destroy the file the fits and the regional payload are built from.
    if not rows:
        sys.exit("no runs with a local recon.nii.gz — refusing to overwrite results/repro_rois.json.\n"
                 "Run this where the harmonization recons and data/harmonization/_align live "
                 "(scripts/repro_slurm/post.slurm), not on a checkout without the volumes.")
    out = {"target": target, "roi_labels": {str(k): v for k, v in ROI_LABELS.items()},
           "runs": rows}
    (RESULTS / "repro_rois.json").write_text(json.dumps(out, indent=2) + "\n")
    print(f"wrote {RESULTS / 'repro_rois.json'} ({len(rows)} runs)")


# ---------------------------------------------------------------------------------------------------
# fits
# ---------------------------------------------------------------------------------------------------

def tls_fit(x: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    """Orthogonal (total-least-squares) line fit y = a x + b — the first principal component of the
    centred (x, y) cloud, equivalent to MATLAB linortfit2 as used in Marta's analysis.

    Returns (inf, nan) on a degenerate/non-convergent fit (a vertical cloud, or an SVD that fails to
    converge on pathological input) rather than raising — one bad pipeline pair must not sink the
    whole fits run."""
    if not (np.all(np.isfinite(x)) and np.all(np.isfinite(y))):
        return float("inf"), float("nan")
    xm, ym = x.mean(), y.mean()
    u = np.stack([x - xm, y - ym])
    try:
        _, _, vt = np.linalg.svd(u.T, full_matrices=False)
    except np.linalg.LinAlgError:
        return float("inf"), float("nan")
    vx, vy = vt[0]
    if abs(vx) < 1e-12:
        return float("inf"), float("nan")
    a = vy / vx
    return float(a), float(ym - a * xm)


def _pair_metrics(vx: dict, vy: dict) -> "dict | None":
    # Only ROIs finite in BOTH acquisitions — a NaN/inf ROI mean (from a pathological recon) would
    # otherwise crash the SVD or poison the correlation.
    common = [k for k in sorted(set(vx) & set(vy))
              if np.isfinite(vx[k]) and np.isfinite(vy[k])]
    if len(common) < MIN_PAIR_ROIS:
        return None
    x = np.array([vx[k] for k in common])
    y = np.array([vy[k] for k in common])
    # A degenerate cloud (one acquisition's ROI values nearly constant — a pipeline that collapsed
    # its χ contrast) has no dynamic range to fit a slope to; the TLS slope then explodes to a
    # non-physical value. Reject rather than store a 1e12 "slope". SLOPE_DEV_CAP mirrors the web's
    # plausibility filter: |a-1| > 2 (slope outside [-1, 3]) is a failed fit, not reproducibility.
    if x.std() < 1e-6 or y.std() < 1e-6:
        return None
    a, b = tls_fit(x, y)
    if not np.isfinite(a) or abs(a - 1) > SLOPE_DEV_CAP:
        return None
    diffs = y - x
    r = float(np.corrcoef(x, y)[0, 1]) if len(common) > 2 else float("nan")
    return {"slope": round(a, 4), "intercept_ppm": round(b, 6),
            "abs_slope_dev": round(abs(a - 1), 4), "pearson_r": round(r, 4),
            "ba_bias_ppm": round(float(diffs.mean()), 6),
            "ba_loa_ppm": round(float(1.96 * diffs.std()), 6),
            "n_rois": len(common)}


def _roi_source() -> tuple[str, list[dict]]:
    """Where the per-run ROI means come from: results/repro_rois.json (the whole-index Bunya stats
    output) when present, else the run rows in results/index.json that carry a `rois` field (the
    per-job CI flow, where each score job wrote its own ROI means and they were merged into index).
    Returns (target, [rows with pipeline/acq/rois])."""
    rj = RESULTS / "repro_rois.json"
    if rj.exists():
        data = json.loads(rj.read_text())
        return data["target"], list(data["runs"].values())
    idx = json.loads((RESULTS / "index.json").read_text())
    rows = idx.get("runs", idx) if isinstance(idx, dict) else idx
    target = json.loads((ALIGN / "target.json").read_text())["target"] if (ALIGN / "target.json").exists() else None
    return target, [r for r in rows if r.get("track") == "repro" and r.get("rois") and r.get("pipeline")]


def live_algo_slugs() -> set[str]:
    """Method slugs the manifest still defines.

    A method REMOVED from web/algorithms.json is gone from QSM-CI (msmv), so re-publishing its
    pipelines on every harvest would keep a retired method alive on the site. `hidden: true` is a
    different state — a parked submission (the MATLAB amp-pe, superseded by the Rust port but kept
    revivable) — so those stay in the payload and the web keeps them out of sight.
    """
    p = ROOT / "web" / "algorithms.json"
    if not p.exists():
        return set()
    return {a["slug"] for a in json.loads(p.read_text()).get("algorithms", []) if a.get("slug")}


def drop_retired(pipelines: list[str], live: set[str], what: str) -> list[str]:
    """Filter '+'-joined pipeline ids to those built only from methods still in the manifest."""
    if not live:                                   # no manifest to check against: publish everything
        return pipelines
    kept = [p for p in pipelines if all(s in live for s in p.split("+"))]
    gone = sorted({s for p in pipelines if p not in set(kept) for s in p.split("+") if s not in live})
    if gone:
        print(f"skipping {len(pipelines) - len(kept)} {what} built on methods no longer in "
              f"algorithms.json: {', '.join(gone)}")
    return kept


def cmd_fits(args) -> None:
    target, rows = _roi_source()
    acqs = repro_acquisitions()
    # (pipeline, acq-id) -> roi means
    by_pa: dict[tuple, dict] = {}
    for row in rows:
        by_pa[(row["pipeline"], row["acq"])] = row["rois"]
    pipelines = drop_retired(sorted({p for p, _ in by_pa}), live_algo_slugs(), "pipeline(s)")
    scanners = ("prisma", "cima")
    protocols = sorted({a["protocol"] for a in acqs.values()})
    runs_ids = ("run1", "run2", "run3")

    def rois(p, scanner, protocol, run):
        return by_pa.get((p, f"{scanner}-{protocol}-{run}"))

    out = {"target": target, "pipelines": {}}
    for p in pipelines:
        node = {"test_retest": {}, "inter_scanner": {}, "inter_protocol": {}}
        # test-retest: same scanner+protocol, run pairs
        for sc in scanners:
            for pr in protocols:
                pairs = {}
                for i, ra in enumerate(runs_ids):
                    for rb in runs_ids[i + 1:]:
                        va, vb = rois(p, sc, pr, ra), rois(p, sc, pr, rb)
                        if va and vb and (m := _pair_metrics(va, vb)):
                            pairs[f"{ra}-{rb}"] = m
                if pairs:
                    node["test_retest"][f"{sc}-{pr}"] = pairs
        # inter-scanner: same protocol+run, prisma vs cima
        for pr in protocols:
            pairs = {}
            for run in runs_ids:
                va, vb = rois(p, "prisma", pr, run), rois(p, "cima", pr, run)
                if va and vb and (m := _pair_metrics(va, vb)):
                    pairs[run] = m
            if pairs:
                node["inter_scanner"][pr] = pairs
        # inter-protocol: same scanner+run, each protocol vs bridge
        for sc in scanners:
            for pr in protocols:
                if pr == "bridge":
                    continue
                pairs = {}
                for run in runs_ids:
                    va, vb = rois(p, sc, "bridge", run), rois(p, sc, pr, run)
                    if va and vb and (m := _pair_metrics(va, vb)):
                        pairs[run] = m
                if pairs:
                    node["inter_protocol"][f"{sc}-{pr}"] = pairs

        # Headline aggregate per comparison class: MEDIAN |a-1| (robust — degenerate pairs are
        # already dropped by _pair_metrics, but the median is the honest central tendency across the
        # spread of a pipeline's pairs, matching what the web shows). Key kept `_mean_` for backward
        # compatibility with any existing reader; the value is the median.
        for cls in ("test_retest", "inter_scanner", "inter_protocol"):
            devs = [m["abs_slope_dev"] for grp in node[cls].values() for m in grp.values()]
            node[f"{cls}_mean_abs_slope_dev"] = round(float(np.median(devs)), 4) if devs else None
        out["pipelines"][p] = node

    (RESULTS / "repro.json").write_text(json.dumps(out, indent=2) + "\n")
    n = len(out["pipelines"])
    print(f"wrote {RESULTS / 'repro.json'} ({n} pipelines)")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("register", help="rigid-register acquisitions to the target")
    r.add_argument("--target", default=DEFAULT_TARGET)
    r.add_argument("--target-only", action="store_true",
                   help="write only the target grid (for a one-time prep job); per-job stats registers "
                        "each acquisition itself")
    r.add_argument("--force", action="store_true")
    s = sub.add_parser("seg", help="segment the target (mri_synthseg via docker) or install --seg")
    s.add_argument("--seg", type=Path, default=None)
    s.add_argument("--image", default="freesurfer/freesurfer:7.4.1",
                   help="FreeSurfer image providing license-free mri_synthseg")
    s.add_argument("--force", action="store_true")
    st = sub.add_parser("stats", help="per-ROI means for every collected repro run")
    st.add_argument("--runs", default=None,
                    help="per-job: compute ROI means for the runs in this pipeline.py --runs-out "
                         "file and write them back into it (registers its acquisition on the fly), "
                         "instead of the whole index -> repro_rois.json")
    sub.add_parser("fits", help="pairwise ax+b fits -> results/repro.json")
    args = ap.parse_args()
    {"register": cmd_register, "seg": cmd_seg, "stats": cmd_stats, "fits": cmd_fits}[args.cmd](args)


if __name__ == "__main__":
    main()
