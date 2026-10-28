#!/usr/bin/env python3
"""Reproducibility evaluation for the no-ground-truth harmonization track.

The `repro` track reconstructs each subject from many acquisitions (scanner x protocol x run), in
two independent cohorts (the registry's `group`, see scripts/repro_format.py REPRO_GROUPS): the EMTP
traveling heads (six subjects, KKI Philips plus GE/Siemens/Philips sessions at other sites) and the
MGH pilot (one subject, two Siemens scanners). There is no truth map; the question is how
reproducible each pipeline's χ values are across acquisitions of the same subject — the analysis Marta Lancione ran with two pipelines (per-ROI orthogonal ax+b fits,
Bland-Altman agreement), generalized over the whole QSM-CI combination matrix.

Stages (subcommands), all idempotent:

  register   Rigid-register every acquisition's first-echo magnitude to its SUBJECT's target
             acquisition (the registry entry with `repro_target: true`). Transforms land in
             data/harmonization/_align/<acq>.tfm, each target's grid in _align/<subject>/.
             Needs SimpleITK.
  seg        SynthSeg each target's first-echo magnitude -> _align/<subject>/dseg.nii.gz (docker or
             apptainer), or install an externally produced segmentation via --seg. One segmentation
             per subject defines the ROIs for every comparison of that subject (per Marta's method),
             so ROI definitions can't drift between runs.
  stats      For every collected repro run (results/index.json + results/<id>/recon.nii.gz):
             resample its χ map into target space, reference it to the whole-brain mean, and record
             per-ROI means -> results/repro_rois.json. ROIs with <90% valid coverage are dropped
             (brain coverage differs between acquisitions).
  fits       Pairwise comparisons per pipeline, always within one subject, written per cohort
             -> results/repro.json (traveling heads), results/repro_pilot.json (MGH pilot), each
             with its fit columns (the web payloads):
               test-retest      same scanner+protocol, run i vs run j
               inter-scanner    same protocol, every pair of scanners the subject visited and every
                                pair of runs (sessions on two scanners are on different days, so run
                                numbers do not correspond between them)
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
import subprocess
import sys
from pathlib import Path

import nibabel as nib
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from repro_format import (FIT_DECIMALS, REPRO_GROUPS, SUMMARY_FIELDS, fit_files, group_of,  # noqa: E402
                           payload_names, write_columns)

ROOT = Path(__file__).resolve().parent.parent
ALIGN = ROOT / "data" / "harmonization" / "_align"
RESULTS = ROOT / "results"

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


ACQ_FIELDS = ("subject", "scanner", "protocol", "run")


def repro_acquisitions() -> dict[str, dict]:
    """The repro-track registry entries: id -> {subject, scanner, protocol, run, group, target, path}.
    `group` is the cohort (repro_format.REPRO_GROUPS) the acquisition belongs to."""
    reg = json.loads((ROOT / "scripts" / "datasets.json").read_text())
    out = {}
    for key, v in reg.items():
        if v.get("track") != "repro":
            continue
        missing = [f for f in ACQ_FIELDS if not v.get(f)]
        if missing:
            raise SystemExit(f"repro acquisition {key} lacks {', '.join(missing)} in scripts/datasets.json")
        if group_of(v) not in REPRO_GROUPS:
            raise SystemExit(f"repro acquisition {key} names group {group_of(v)!r}, which "
                             f"scripts/repro_format.py REPRO_GROUPS does not define")
        out[key] = {**{f: v[f] for f in ACQ_FIELDS}, "group": group_of(v),
                    "target": bool(v.get("repro_target")), "path": ROOT / v["path"]}
    return out


def acquisitions_by_group(acqs: dict[str, dict]) -> dict[str, dict[str, dict]]:
    """{cohort: {id: acquisition}} in REPRO_GROUPS order, cohorts without acquisitions left out. A
    subject belongs to exactly one cohort (pairs never cross subjects, so neither may a cohort)."""
    by: dict[str, dict] = {g: {} for g in REPRO_GROUPS}
    for k, a in acqs.items():
        by[a["group"]][k] = a
    owner: dict[str, str] = {}
    for g, mine in by.items():
        for a in mine.values():
            if owner.setdefault(a["subject"], g) != g:
                raise SystemExit(f"subject {a['subject']} has acquisitions in two groups "
                                 f"({owner[a['subject']]}, {g}); a subject belongs to one cohort")
    return {g: mine for g, mine in by.items() if mine}


def subject_targets(acqs: dict[str, dict]) -> dict[str, str]:
    """subject -> its registration target acquisition (exactly one `repro_target` per subject)."""
    targets: dict[str, list[str]] = {}
    for key, a in acqs.items():
        targets.setdefault(a["subject"], [])
        if a["target"]:
            targets[a["subject"]].append(key)
    bad = {s: t for s, t in targets.items() if len(t) != 1}
    if bad:
        raise SystemExit(f"each subject needs exactly one repro_target acquisition: {bad}")
    return {s: t[0] for s, t in sorted(targets.items())}


def subject_align(subject: str) -> Path:
    """Per-subject reference frame: target.json, target_mag_e1.nii.gz, dseg.nii.gz."""
    return ALIGN / subject


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
    # Per-process temp names: the shards of one acquisition run `stats --runs` in parallel and may
    # all register it at once; a shared name let the first to finish delete the others' input.
    mov_nii = tfm_path.parent / f"_mov_{key}.{os.getpid()}.nii.gz"
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
    tmp_tfm = tfm_path.with_name(f"{tfm_path.stem}.{os.getpid()}.tfm")
    sitk.WriteTransform(tfm, str(tmp_tfm))
    os.replace(tmp_tfm, tfm_path)       # atomic: a concurrent shard never reads a half-written .tfm
    mov_nii.unlink()
    return f"metric={reg.GetMetricValue():.4f} ({reg.GetOptimizerIteration()} iters)"


def cmd_register(args) -> None:
    import SimpleITK as sitk  # deferred: only this stage needs it

    acqs = repro_acquisitions()
    targets = subject_targets(acqs)
    if args.subject and args.subject not in targets:
        raise SystemExit(f"unknown subject '{args.subject}' (have {', '.join(targets)})")
    for subject, target in targets.items():
        if args.subject and subject != args.subject:
            continue
        align = subject_align(subject)
        align.mkdir(parents=True, exist_ok=True)
        (align / "target.json").write_text(json.dumps({"subject": subject, "target": target}) + "\n")
        tgt_nii = align / "target_mag_e1.nii.gz"
        nib.save(first_echo_magnitude(acqs[target]["path"]), str(tgt_nii))
        fixed = sitk.ReadImage(str(tgt_nii), sitk.sitkFloat32)

        # Prep-only: just the target grid (+ its identity transform) so a one-time `prep` job can
        # build each reference frame (target_mag_e1 + dseg via seg) without fetching every
        # acquisition — the per-job `stats --runs` path registers each acquisition itself.
        if getattr(args, "target_only", False):
            sitk.WriteTransform(sitk.Euler3DTransform(), str(ALIGN / f"{target}.tfm"))
            print(f"  {subject}: target grid {target} written (target-only)")
            continue

        for key, acq in sorted(acqs.items()):
            if acq["subject"] != subject:
                continue
            tfm_path = ALIGN / f"{key}.tfm"
            if tfm_path.exists() and not args.force:
                continue
            print(f"  {key}: {_register_one(key, acq['path'], fixed, tfm_path, key == target, sitk)}")


# ---------------------------------------------------------------------------------------------------
# seg
# ---------------------------------------------------------------------------------------------------

def cmd_seg(args) -> None:
    subjects = subject_targets(repro_acquisitions())
    if args.seg:  # externally produced segmentation of ONE subject's target first-echo magnitude
        if not args.subject:
            raise SystemExit("--seg needs --subject (which subject's target it segments)")
        dseg = subject_align(args.subject) / "dseg.nii.gz"
        src = nib.load(str(args.seg))
        nib.save(nib.Nifti1Image(np.asanyarray(src.dataobj).astype(np.int16), src.affine), str(dseg))
        print(f"installed {args.seg} -> {dseg}")
        return
    import SimpleITK as sitk
    for subject in subjects:
        if args.subject and subject != args.subject:
            continue
        align = subject_align(subject)
        dseg = align / "dseg.nii.gz"
        if dseg.exists() and not args.force:
            print(f"{dseg} exists (use --force to redo)")
            continue
        # mri_synthseg (robust, contrast-agnostic) on the target magnitude, via the official
        # FreeSurfer image — mri_synthseg is one of the license-free tools, and it emits standard
        # FreeSurfer aseg labels (the ids in ROI_LABELS). Runs on any GRE/EPI contrast, which is
        # why it fits here.
        synth = ["mri_synthseg", "--i", "/data/target_mag_e1.nii.gz", "--o", "/data/dseg_synthseg.nii.gz",
                 "--robust", "--threads", "4"]
        if args.runner == "apptainer":
            cmd = ["apptainer", "exec", "--bind", f"{align}:/data", f"docker://{args.image}", *synth]
        else:
            cmd = ["docker", "run", "--rm", "--user", f"{os.getuid()}:{os.getgid()}",
                   "-v", f"{align}:/data", args.image, *synth]
        subprocess.run(cmd, check=True)
        # SynthSeg resamples to its own 1mm grid; bring labels back onto the target grid.
        fixed = sitk.ReadImage(str(align / "target_mag_e1.nii.gz"))
        seg = sitk.ReadImage(str(align / "dseg_synthseg.nii.gz"))
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


class _Frames:
    """Each subject's reference frame (target grid + segmentation + ROI masks), loaded on first use
    so a per-job stats run only reads the subject it needs."""

    def __init__(self, sitk):
        self.sitk = sitk
        self._cache: dict[str, tuple] = {}

    def __call__(self, subject: str) -> tuple:
        if subject not in self._cache:
            sitk, align = self.sitk, subject_align(subject)
            target = json.loads((align / "target.json").read_text())["target"]
            fixed = sitk.ReadImage(str(align / "target_mag_e1.nii.gz"), sitk.sitkFloat32)
            dseg = np.rint(sitk.GetArrayFromImage(sitk.ReadImage(str(align / "dseg.nii.gz")))).astype(int)
            roi_masks = {lab: dseg == lab for lab in ROI_LABELS if (dseg == lab).sum() >= 50}
            self._cache[subject] = (target, fixed, dseg, roi_masks)
        return self._cache[subject]


def cmd_stats(args) -> None:
    import SimpleITK as sitk

    frames = _Frames(sitk)
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
            target, fixed, dseg, roi_masks = frames(acqs[acq]["subject"])
            if acq not in tcache:                  # register this acquisition to its target once
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
        _, fixed, dseg, roi_masks = frames(acqs[acq]["subject"])
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
    out = {"targets": subject_targets(acqs), "roi_labels": {str(k): v for k, v in ROI_LABELS.items()},
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


def _pair_metrics(vx: dict, vy: dict) -> "tuple[dict | None, dict | None]":
    """(metrics, rejection) for one acquisition pair — exactly one of the two is None.

    The rejection carries the reason and, where there was one, the offending slope, so repro.json can
    state how often this fires instead of the site having to hand-wave "degenerate fits are excluded".
    """
    # Only ROIs finite in BOTH acquisitions — a NaN/inf ROI mean (from a pathological recon) would
    # otherwise crash the SVD or poison the correlation.
    common = [k for k in sorted(set(vx) & set(vy))
              if np.isfinite(vx[k]) and np.isfinite(vy[k])]
    if len(common) < MIN_PAIR_ROIS:
        return None, {"why": "too_few_rois", "n_rois": len(common)}
    x = np.array([vx[k] for k in common])
    y = np.array([vy[k] for k in common])
    # A degenerate cloud (one acquisition's ROI values nearly constant — a pipeline that collapsed
    # its χ contrast) has no dynamic range to fit a slope to; the TLS slope then explodes to a
    # non-physical value. Reject rather than store a 1e12 "slope". SLOPE_DEV_CAP mirrors the web's
    # plausibility filter: |a-1| > 2 (slope outside [-1, 3]) is a failed fit, not reproducibility.
    if x.std() < 1e-6 or y.std() < 1e-6:
        return None, {"why": "flat_roi_cloud"}
    a, b = tls_fit(x, y)
    if not np.isfinite(a):
        return None, {"why": "non_finite_slope"}
    if abs(a - 1) > SLOPE_DEV_CAP:
        return None, {"why": "slope_cap", "slope": round(float(a), 4), "abs_slope_dev": round(abs(a - 1), 4)}
    diffs = y - x
    r = float(np.corrcoef(x, y)[0, 1]) if len(common) > 2 else float("nan")
    return {"slope": round(a, 4), "intercept_ppm": round(b, 6),
            "abs_slope_dev": round(abs(a - 1), 4), "pearson_r": round(r, 4),
            "ba_bias_ppm": round(float(diffs.mean()), 6),
            "ba_loa_ppm": round(float(1.96 * diffs.std()), 6),
            "n_rois": len(common)}, None


def _roi_source() -> list[dict]:
    """Where the per-run ROI means come from: results/repro_rois.json (the whole-index Bunya stats
    output) when present, else the run rows in results/index.json that carry a `rois` field (the
    per-job CI flow, where each score job wrote its own ROI means and they were merged into index).
    Returns [rows with pipeline/acq/rois]."""
    rj = RESULTS / "repro_rois.json"
    if rj.exists():
        return list(json.loads(rj.read_text())["runs"].values())
    idx = json.loads((RESULTS / "index.json").read_text())
    rows = idx.get("runs", idx) if isinstance(idx, dict) else idx
    return [r for r in rows if r.get("track") == "repro" and r.get("rois") and r.get("pipeline")]


def live_algo_slugs() -> set[str]:
    """Method slugs the manifest still defines.

    A method REMOVED from web/algorithms.json is gone from QSM-CI, so re-publishing its
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


def comparison_plan(acqs: dict[str, dict]) -> list[tuple[str, str, str, str, str]]:
    """Every comparison the design calls for, as (class, group, key, acq_a, acq_b). Pairs never
    cross subjects: an inter-scanner comparison is the same person on two scanners.

      test_retest     group <subject>/<scanner>-<protocol>, key <runA>-<runB>
      inter_scanner   group <subject>/<protocol>,           key <scannerA>-vs-<scannerB>-<runA>-<runB>
      inter_protocol  group <subject>/<scanner>-<protocol>, key <run>  (protocol vs bridge)
    """
    by = {(a["subject"], a["scanner"], a["protocol"], a["run"]): k for k, a in acqs.items()}
    subjects = sorted({a["subject"] for a in acqs.values()})
    plan: list[tuple[str, str, str, str, str]] = []
    for subj in subjects:
        mine = [a for a in acqs.values() if a["subject"] == subj]
        # Registry order, not alphabetical: it keeps the pilot's prisma-vs-cima direction and puts
        # each traveling head's home (KKI) session first, so slopes read "other scanner vs home".
        scanners = list(dict.fromkeys(a["scanner"] for a in mine))
        protocols = sorted({a["protocol"] for a in mine})
        runs = sorted({a["run"] for a in mine})
        for sc in scanners:                                    # test-retest: same scanner+protocol
            for pr in protocols:
                for i, ra in enumerate(runs):
                    for rb in runs[i + 1:]:
                        plan.append(("test_retest", f"{subj}/{sc}-{pr}", f"{ra}-{rb}",
                                     by.get((subj, sc, pr, ra)), by.get((subj, sc, pr, rb))))
        # inter-scanner: same protocol, every run on one scanner against every run on the other.
        # The two sessions are on different days, so "run 1" on one scanner has no closer link to
        # "run 1" on the other than to any other run; pairing all of them avoids an arbitrary choice.
        for pr in protocols:
            for i, sa in enumerate(scanners):
                for sb in scanners[i + 1:]:
                    for ra in runs:
                        for rb in runs:
                            plan.append(("inter_scanner", f"{subj}/{pr}", f"{sa}-vs-{sb}-{ra}-{rb}",
                                         by.get((subj, sa, pr, ra)), by.get((subj, sb, pr, rb))))
        for sc in scanners:                                    # inter-protocol: each protocol vs bridge
            for pr in protocols:
                if pr == "bridge":
                    continue
                for run in runs:
                    plan.append(("inter_protocol", f"{subj}/{sc}-{pr}", run,
                                 by.get((subj, sc, "bridge", run)), by.get((subj, sc, pr, run))))
    # A comparison whose acquisition does not exist at all (prisma pulseq-offline run2 was never
    # acquired) is not an exclusion, so it is not counted as one anywhere.
    return [c for c in plan if c[3] and c[4]]


def cmd_fits(args) -> None:
    """One payload set per cohort (repro_format.REPRO_GROUPS): results/<stem>.json + its fit columns.
    Each cohort's comparisons, summaries, pair counts and rejections cover its own acquisitions only,
    and its pipelines are the ones with at least one run on them."""
    rows = _roi_source()
    acqs = repro_acquisitions()
    # (pipeline, acq-id) -> roi means
    by_pa: dict[tuple, dict] = {}
    for row in rows:
        by_pa[(row["pipeline"], row["acq"])] = row["rois"]
    live = live_algo_slugs()
    written = 0
    for group, mine in acquisitions_by_group(acqs).items():
        pipelines = drop_retired(sorted({p for p, a in by_pa if a in mine}), live,
                                 f"{group} pipeline(s)")
        if not pipelines:
            # Don't overwrite a cohort's good payload with an empty one (no runs harvested for it yet).
            print(f"{group}: no runs on its acquisitions — left {payload_names(group)['repro']} as it is")
            continue
        write_fits(group, mine, pipelines, by_pa)
        written += 1
    if not written:
        sys.exit("no harmonization runs to fit — nothing written.")


def write_fits(group: str, acqs: dict[str, dict], pipelines: list[str], by_pa: dict) -> dict:
    """Fit every comparison of one cohort (`acqs`) for `pipelines`; write results/<stem>.json and its
    fit columns. Returns the index written."""
    plan = comparison_plan(acqs)
    names = payload_names(group)

    # The web reads pair membership and acquisition metadata from here rather than parsing ids.
    comparisons: dict[str, dict] = {}
    for cls, grp, key, a_id, b_id in plan:
        comparisons.setdefault(cls, {}).setdefault(grp, {})[key] = [a_id, b_id]
    # Per-pair stats are columns over [pipeline x pair] (repro_format.py), so each pipeline's row is
    # filled in plan order and a pair without a fit stays None (NaN on disk).
    n_pairs = len(plan)
    files = fit_files(REPRO_GROUPS[group]["stem"])
    fields = [f for _, fs in files for f in fs]
    cols = {f: [None] * (len(pipelines) * n_pairs) for f in fields}
    summary: dict[str, list] = {f: [] for f in SUMMARY_FIELDS}
    rejected_by: dict[str, list] = {}
    for i, p in enumerate(pipelines):
        devs = {"test_retest": [], "inter_scanner": [], "inter_protocol": []}
        possible = {"test_retest": 0, "inter_scanner": 0, "inter_protocol": 0}
        rejected: list[dict] = []
        no_recon = 0
        for j, (cls, grp, key, a_id, b_id) in enumerate(plan):
            possible[cls] += 1
            va, vb = by_pa.get((p, a_id)), by_pa.get((p, b_id))
            if not va or not vb:
                no_recon += 1               # this pipeline failed to reconstruct one of the two
                continue
            m, rej = _pair_metrics(va, vb)
            if m:
                for f in fields:
                    cols[f][i * n_pairs + j] = m[f]
                devs[cls].append(m["abs_slope_dev"])
            else:
                rejected.append({"pair": j, **rej})

        # Headline aggregates per comparison class. Both are reported because they answer different
        # questions and, on the bimodal pipelines, disagree: the MEDIAN is the typical pair (robust —
        # one bad protocol can't move it), the MEAN is the expected error over the whole pair set and
        # so is the one that notices when a pipeline fails on a subset. Degenerate fits are already
        # dropped upstream by _pair_metrics, so neither is defending against outright garbage.
        # `{cls}_mean_abs_slope_dev` was historically the MEDIAN under a misleading name; it is now a
        # genuine mean, and readers wanting the old value must use `{cls}_median_abs_slope_dev`.
        for cls, d in devs.items():
            summary[f"{cls}_median_abs_slope_dev"].append(round(float(np.median(d)), 4) if d else None)
            summary[f"{cls}_mean_abs_slope_dev"].append(round(float(np.mean(d)), 4) if d else None)
            summary[f"{cls}_n_pairs"].append(len(d))
            summary[f"{cls}_n_possible"].append(possible[cls])
        # Per-pipeline so the site can total them over whatever pipelines it is actually showing
        # (methods retired from the manifest are hidden there) rather than over a fixed headline.
        summary["n_possible"].append(sum(possible.values()))
        summary["n_rejected"].append(len(rejected))
        summary["n_no_recon"].append(no_recon)
        if rejected:
            rejected_by[p] = rejected

    fits = write_columns(RESULTS, [(name, {f: cols[f] for f in fs}) for name, fs in files],
                         (len(pipelines), n_pairs), {f: FIT_DECIMALS[f] for f in fields})
    out = {"group": group,
           "targets": subject_targets(acqs),
           "acquisitions": {k: {f: a[f] for f in ACQ_FIELDS} for k, a in sorted(acqs.items())},
           "comparisons": comparisons,
           "exclusion_rules": {"slope_dev_cap": SLOPE_DEV_CAP, "min_pair_rois": MIN_PAIR_ROIS,
                               "min_roi_coverage": MIN_ROI_COVERAGE},
           "pairs": [{"class": c, "group": g, "key": k, "a": a, "b": b} for c, g, k, a, b in plan],
           "pipelines": pipelines,
           "summary": summary,
           "rejected": rejected_by,
           "fits": fits}
    (RESULTS / names["repro"]).write_text(json.dumps(out, separators=(",", ":")) + "\n")
    poss, rej, nore = (sum(summary[f]) for f in ("n_possible", "n_rejected", "n_no_recon"))
    print(f"{group}: wrote {RESULTS / names['repro']} + {', '.join(f['file'] for f in fits['files'])} "
          f"({len(pipelines)} pipelines x {n_pairs} pairs)")
    print(f"  pairs: {poss - rej - nore} kept of {poss} possible "
          f"({rej} rejected fits, {nore} with no reconstruction)")
    return out


def cmd_run_regions(args) -> None:
    """Write results/<run_id>/regions.json for every harmonization run, from repro_rois.json.

    The per-run regional artifact the submission page's Regions tab reads normally rides out of
    pipeline.py during scoring. When the matrix is re-run with a pipeline.py that predates that
    (as the 2026-09 recompute was), every run keeps the regions.json from the PREVIOUS matrix — a
    file whose numbers describe recons that no longer exist.

    Nothing has to be recomputed to fix that: `stats` already wrote per-run, per-ROI n/mean/std/median
    into repro_rois.json's `roi_stats`, which is exactly the block regions.json carries. This is a
    pure transform of that file, so it costs seconds and cannot disagree with the fits built from the
    same source.
    """
    src = RESULTS / "repro_rois.json"
    if not src.exists():
        sys.exit(f"{src} not found — run `repro_eval.py stats` first.")
    runs = json.loads(src.read_text()).get("runs", {})
    labels = {str(k): v for k, v in ROI_LABELS.items()}
    written = skipped = no_stats = 0
    for run_id, row in runs.items():
        stats = row.get("roi_stats")
        if not stats:
            no_stats += 1
            continue
        d = RESULTS / run_id
        if not d.is_dir():
            skipped += 1          # scored elsewhere / cleaned up: nothing to attach the file to
            continue
        block = {"chi": {"labels": {k: labels[k] for k in stats if k in labels}, "recon": stats}}
        (d / "regions.json").write_text(json.dumps(block, indent=2) + "\n")
        written += 1
    print(f"wrote {written} per-run regions.json from {src}")
    if skipped:
        print(f"  {skipped} run(s) had no results/<id>/ directory")
    if no_stats:
        print(f"  {no_stats} run(s) had no roi_stats (re-run `stats` for those)")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("register", help="rigid-register acquisitions to the target")
    r.add_argument("--subject", default=None, help="only this subject (default: every subject)")
    r.add_argument("--target-only", action="store_true",
                   help="write only the target grid (for a one-time prep job); per-job stats registers "
                        "each acquisition itself")
    r.add_argument("--force", action="store_true")
    s = sub.add_parser("seg", help="segment each subject's target (mri_synthseg) or install --seg")
    s.add_argument("--seg", type=Path, default=None)
    s.add_argument("--subject", default=None, help="only this subject (required with --seg)")
    s.add_argument("--runner", choices=("docker", "apptainer"), default="docker")
    s.add_argument("--image", default="freesurfer/freesurfer:7.4.1",
                   help="FreeSurfer image providing license-free mri_synthseg")
    s.add_argument("--force", action="store_true")
    st = sub.add_parser("stats", help="per-ROI means for every collected repro run")
    st.add_argument("--runs", default=None,
                    help="per-job: compute ROI means for the runs in this pipeline.py --runs-out "
                         "file and write them back into it (registers its acquisition on the fly), "
                         "instead of the whole index -> repro_rois.json")
    sub.add_parser("fits", help="pairwise ax+b fits -> results/<stem>.json per cohort")
    sub.add_parser("run-regions", help="per-run results/<id>/regions.json from repro_rois.json")
    args = ap.parse_args()
    {"register": cmd_register, "seg": cmd_seg, "stats": cmd_stats, "fits": cmd_fits,
     "run-regions": cmd_run_regions}[args.cmd](args)


if __name__ == "__main__":
    main()
