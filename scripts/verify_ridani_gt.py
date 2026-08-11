#!/usr/bin/env python3
"""Verify qsm-forward-generated Ridani chi-sep ground truth against the authors'
canonical OSF uploads (project 9xwhz, mirrored by scripts/mirror_ridani_osf.py).

Compares, on the shared native grid (256x320x320 @ 0.64 mm):
  1. voxelwise agreement (Pearson r, mean/p95 |diff|) whole-head / brain / WM
  2. per-ROI means vs (a) the OSF reference maps and (b) paper Table 2
     (Ridani et al., MRM doi:10.1002/mrm.70468)

The reference generator adds UNSEEDED Gaussian texture noise (WM weighting
sigma=0.01 x3 iterations; anisotropic modulation eta ~ N(-0.04, 0.05)), so
voxelwise identity is impossible by construction — the acceptance criteria are
high correlation + ROI means matching Table 2 within the noise floor.

Usage:
  python3 scripts/verify_ridani_gt.py --ours data/ridani-ver --osf data/ridani-osf
"""
import argparse
import json
from pathlib import Path

import nibabel as nib
import numpy as np

# Paper Table 2: ROI-averaged GT susceptibilities (ppm).
# name -> (chi_pos, chi_neg, chi_neg_aniso or None)
TABLE2_MAIN = {
    "Gray matter":       (0.0342, -0.0195, None),
    "Caudate nucleus":    (0.0489, -0.0095, None),
    "Globus pallidus":    (0.1381, -0.0137, None),
    "Putamen":            (0.0455, -0.0099, None),
    "Red nucleus":        (0.1061, -0.0095, None),
    "Dentate nucleus":    (0.1584, -0.0163, None),
    "Substantia nigra":   (0.1145, -0.0124, None),
    "Thalamus":           (0.0473, -0.0316, None),
    "White matter":       (0.0063, -0.0363, -0.0337),
}
TABLE2_WM_SUB = {
    "Body corpus callosum":        (0.0036, -0.0424, -0.0437),
    "Splenium CC":                 (0.0037, -0.0380, -0.0500),
    "Genu CC":                     (0.0010, -0.0413, -0.0466),
    "Ant. limb internal capsule":  (0.0085, -0.0312, -0.0465),
    "Post. limb internal capsule": (0.0008, -0.0354, -0.0655),
    "Superior corona radiata":     (0.0024, -0.0464, -0.0420),
    "Posterior corona radiata":    (0.0023, -0.0440, -0.0530),
    "Anterior corona radiata":     (0.0004, -0.0425, -0.0541),
    "Post. thalamic radiations":   (0.0068, -0.0388, -0.0472),
    "Sup. longitudinal fascicle":  (0.0005, -0.0374, -0.0438),
}


def load(p):
    return np.asarray(nib.load(str(p)).get_fdata(), dtype=np.float64)


def stats(a, b, m):
    a, b = a[m], b[m]
    d = a - b
    r = np.corrcoef(a, b)[0, 1] if a.std() > 0 and b.std() > 0 else np.nan
    return r, d.mean(), np.percentile(np.abs(d), 95)


def roi_means(vol, seg, labels):
    return {lab: float(vol[seg == lab].mean()) for lab in labels if (seg == lab).any()}


def match_labels(ref_vol, seg, table_col, labels):
    """Greedy-match integer labels to named ROIs by nearest reference-map ROI mean
    to the Table 2 value (validates the assumed label order instead of trusting it)."""
    means = roi_means(ref_vol, seg, labels)
    out = {}
    used = set()
    for name, target in table_col.items():
        best = min((l for l in means if l not in used),
                   key=lambda l: abs(means[l] - target), default=None)
        if best is not None:
            out[name] = best
            used.add(best)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ours", type=Path, default=Path("data/ridani-ver"))
    ap.add_argument("--osf", type=Path, default=Path("data/ridani-osf"))
    ap.add_argument("--json", type=Path, default=None, help="also dump results as JSON")
    args = ap.parse_args()

    res = args.osf / "Susceptibility_Separation_Results"
    ref = {
        "chi_pos": load(res / "Chi_positive.nii.gz"),
        "chi_neg_iso": load(res / "Chi_negative.nii.gz"),
        "chi_neg_aniso": load(res / "Chi_negative_with_anisotropy.nii.gz"),
    }
    seg = load(args.osf / "Masks" / "SegmentedModel.nii.gz").round().astype(int)
    brain = load(args.osf / "Masks" / "BrainMask.nii.gz") > 0.5
    fib = load(args.osf / "Masks" / "WM_fibers_seg.nii.gz").round().astype(int)
    wm = seg == 8

    # our maps: gen_chisep --maps-only writes groundtruth/{chi-para,chi-dia}.nii.gz
    # (chi-dia may be stored as a positive magnitude — detect and restore sign).
    def load_ours(variant, name):
        for rel in (f"{variant}/groundtruth/{name}.nii.gz", f"{variant}/{name}.nii.gz",
                    f"{variant}/inputs/{name}.nii.gz"):
            p = args.ours / rel
            if p.exists():
                return load(p), p
        raise FileNotFoundError(f"{name} under {args.ours}/{variant}")

    report = {}
    print(f"{'map':28s} {'scope':6s} {'r':>7s} {'mean diff':>10s} {'p95|diff|':>10s}")
    for variant, ref_key, ours_name in [
        ("aniso", "chi_pos", "chi-para"),
        ("aniso", "chi_neg_aniso", "chi-dia"),
        ("iso", "chi_pos", "chi-para"),
        ("iso", "chi_neg_iso", "chi-dia"),
    ]:
        ours, path = load_ours(variant, ours_name)
        if "dia" in ours_name and ours.min() >= 0 and ref[ref_key].min() < 0:
            ours = -ours  # stored-as-magnitude convention
        for scope, m in [("head", np.abs(ref[ref_key]) + np.abs(ours) > 0),
                         ("brain", brain), ("WM", wm)]:
            r, md, p95 = stats(ours, ref[ref_key], m)
            key = f"{variant}/{ours_name}"
            report.setdefault(key, {})[scope] = {"r": r, "mean_diff": md, "p95_absdiff": p95}
            print(f"{key:28s} {scope:6s} {r:7.4f} {md:10.5f} {p95:10.5f}")

    # ROI means: main ROIs on SegmentedModel (brain labels), WM sub-ROIs on WM_fibers_seg
    main_labels = sorted(set(np.unique(seg[brain])) - {0})
    sub_labels = sorted(set(np.unique(fib)) - {0})
    lab_main = match_labels(ref["chi_pos"], seg, {k: v[0] for k, v in TABLE2_MAIN.items()}, main_labels)
    lab_sub = match_labels(ref["chi_neg_iso"], fib, {k: v[1] for k, v in TABLE2_WM_SUB.items()}, sub_labels)

    ours_pos, _ = load_ours("aniso", "chi-para")
    ours_neg_iso, _ = load_ours("iso", "chi-dia")
    ours_neg_ani, _ = load_ours("aniso", "chi-dia")
    if ours_neg_iso.min() >= 0:
        ours_neg_iso = -ours_neg_iso
    if ours_neg_ani.min() >= 0:
        ours_neg_ani = -ours_neg_ani

    def table(title, table2, labmap, segvol):
        print(f"\n== {title} (ppm; ours vs OSF ref vs paper Table 2) ==")
        print(f"{'ROI':28s} {'lab':>3s} | {'χ+ ours':>8s} {'ref':>8s} {'tab2':>8s} | "
              f"{'χ- ours':>8s} {'ref':>8s} {'tab2':>8s} | {'χ-a ours':>8s} {'ref':>8s} {'tab2':>8s}")
        rows = {}
        for name, (t_pos, t_neg, t_ani) in table2.items():
            lab = labmap.get(name)
            if lab is None:
                continue
            m = segvol == lab
            row = {
                "pos": (ours_pos[m].mean(), ref["chi_pos"][m].mean(), t_pos),
                "neg": (ours_neg_iso[m].mean(), ref["chi_neg_iso"][m].mean(), t_neg),
                "ani": (ours_neg_ani[m].mean(), ref["chi_neg_aniso"][m].mean(), t_ani),
            }
            rows[name] = {k: tuple(None if x is None else float(x) for x in v)
                          for k, v in row.items()}
            f = lambda v: "     ---" if v is None else f"{v:8.4f}"
            print(f"{name:28s} {lab:3d} | {f(row['pos'][0])} {f(row['pos'][1])} {f(row['pos'][2])} | "
                  f"{f(row['neg'][0])} {f(row['neg'][1])} {f(row['neg'][2])} | "
                  f"{f(row['ani'][0])} {f(row['ani'][1])} {f(row['ani'][2])}")
        return rows

    report["roi_main"] = table("Main ROIs", TABLE2_MAIN, lab_main, seg)
    report["roi_wm_sub"] = table("WM sub-ROIs", TABLE2_WM_SUB, lab_sub, fib)
    report["label_maps"] = {"main": {k: int(v) for k, v in lab_main.items()},
                            "wm_sub": {k: int(v) for k, v in lab_sub.items()}}

    if args.json:
        args.json.write_text(json.dumps(report, indent=2))
        print(f"\nwrote {args.json}")


if __name__ == "__main__":
    main()
