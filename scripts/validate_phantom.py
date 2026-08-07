#!/usr/bin/env python3
"""validate_phantom — measure whether a χ-separation phantom can actually discriminate methods.

A source-separation benchmark is only meaningful if recovering χ+/χ- from the *provided* inputs is
non-trivial. This harness runs the cheap diagnostics that tell you that, before spending hours on a
real separator:

  1. Null model      — the closed-form analytic solve χ± = (χ_total ± R2'/Dr)/2, scored with the
                       leaderboard's metrics. It can score high xSIM yet high NRMSE (anisotropy shows
                       up in the magnitude error, not the structure), so triviality is judged on the
                       detrended NRMSE it reaches: if that is near-zero, the split is closed-form and
                       the board only measures who reproduces this arithmetic.
  2. Degeneracy      — how much of R2' is explained by a single global Dr·(|χ+|+|χ-|). If ~all of it,
                       R2' carries no information beyond χ_total and the split is closed-form.
  3. Co-location     — how often χ+ and χ- are BOTH large in the same voxel (the cancellation regime).
                       Near-zero means no signal-domain method can gain over a field-domain shortcut.
  4. Multi-comp sig  — does the multi-echo magnitude deviate from a mono-exponential in a way that
                       tracks source content? Near-zero means the signal carries nothing to separate.

Usage:
    python scripts/validate_phantom.py data/sim/chisep [--dr 137,114] [--json out.json]

Expects the QSM-CI dataset layout: <dir>/inputs/{chimap,r2prime,mask[,magnitude]}.nii.gz and
<dir>/groundtruth/{chi-para,chi-dia}.nii.gz (chi-dia stored as a positive magnitude).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import nibabel as nib

# Reuse the exact scoring the leaderboard uses so null-model numbers are directly comparable.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "eval"))
from qsm_eval import xsim, nrmse_challenge  # noqa: E402


def _load(p: Path) -> np.ndarray:
    return nib.load(str(p)).get_fdata()


def null_model(chi, r2p, mask, gt_pos, gt_neg, dr_values):
    """Closed-form χ± = (χ_total ± R2'/Dr)/2 for each Dr; scored vs ground truth."""
    rows = []
    for dr in dr_values:
        pos = np.clip((chi + r2p / dr) / 2.0, 0, None)
        negmag = np.clip((r2p / dr - chi) / 2.0, 0, None)
        pn, pn_dt = nrmse_challenge(pos, gt_pos, mask)
        dn, dn_dt = nrmse_challenge(negmag, gt_neg, mask)
        rows.append({
            "dr": dr,
            "para_xsim": xsim(pos, gt_pos, mask),
            "dia_xsim": xsim(negmag, gt_neg, mask),
            "para_nrmse": pn, "dia_nrmse": dn,
            "para_nrmse_detrend": pn_dt, "dia_nrmse_detrend": dn_dt,
        })
    return rows


def degeneracy(r2p, mask, gt_pos, gt_neg):
    """Fit R2' ~ Dr·(|χ+|+|χ-|) with a single global Dr; report unexplained fraction.

    A construction-agnostic test: whatever Dr the phantom used, if one global scalar explains R2'
    then R2' is a deterministic function of the sources and the split is closed-form recoverable."""
    src = (gt_pos + gt_neg)[mask]      # |χ+| + |χ-|  (gt_neg is a positive magnitude)
    y = r2p[mask]
    dr_fit = float(np.dot(src, y) / np.dot(src, src)) if np.dot(src, src) > 0 else float("nan")
    resid = y - dr_fit * src
    unexplained = float(np.std(resid) / (np.std(y) + 1e-12))
    return {"dr_fit": dr_fit, "unexplained_frac": unexplained}


def colocation(mask, gt_pos, gt_neg, thresholds=(0.01, 0.02, 0.03, 0.05, 0.10)):
    """Distribution of min(χ+, |χ-|): the cancellation regime signal-domain methods need."""
    both = np.minimum(gt_pos, gt_neg)[mask]
    return {
        "max_ppm": float(both.max()),
        "coverage": {f">{t}ppm": float((both > t).mean()) for t in thresholds},
    }


def multicompartment_signature(mag, mask, gt_pos, gt_neg, te):
    """Non-mono-exponential magnitude structure that tracks source content.

    Per-voxel linear fit of log-magnitude vs TE (mono-exponential => zero residual up to noise); a
    genuine multi-compartment beat leaves a residual that correlates with total source content."""
    if mag is None or mag.ndim != 4 or mag.shape[-1] < 3:
        return None
    lm = np.log(np.clip(mag, 1e-9, None))
    A = np.vstack([te, np.ones_like(te)]).T
    coef, *_ = np.linalg.lstsq(A, lm[mask].T, rcond=None)
    pred = (A @ coef).T
    resid = np.sqrt(((lm[mask] - pred) ** 2).mean(axis=1))
    src = (gt_pos + gt_neg)[mask]
    corr = float(np.corrcoef(resid, src)[0, 1]) if resid.std() > 0 and src.std() > 0 else 0.0
    return {"resid_median": float(np.median(resid)), "corr_with_source": corr}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dataset", type=Path, help="dataset dir with inputs/ and groundtruth/")
    ap.add_argument("--dr", default="137,114", help="comma-separated Dr values for the null model")
    ap.add_argument("--json", type=Path, default=None, help="write the full report as JSON here")
    args = ap.parse_args()

    d = args.dataset
    chi = _load(d / "inputs" / "chimap.nii.gz")
    r2p = _load(d / "inputs" / "r2prime.nii.gz")
    mask = _load(d / "inputs" / "mask.nii.gz") > 0
    gt_pos = _load(d / "groundtruth" / "chi-para.nii.gz")
    gt_neg = _load(d / "groundtruth" / "chi-dia.nii.gz")  # positive magnitude
    mag_path = d / "inputs" / "magnitude.nii.gz"
    mag = _load(mag_path) if mag_path.exists() else None
    te = None
    params_path = d / "inputs" / "params.json"
    if mag is not None and params_path.exists():
        te = np.asarray(json.loads(params_path.read_text())["TE"], float)

    dr_values = [float(x) for x in args.dr.split(",")]
    report = {
        "dataset": str(d),
        "null_model": null_model(chi, r2p, mask, gt_pos, gt_neg, dr_values),
        "degeneracy": degeneracy(r2p, mask, gt_pos, gt_neg),
        "colocation": colocation(mask, gt_pos, gt_neg),
        "multicompartment": multicompartment_signature(mag, mask, gt_pos, gt_neg, te) if te is not None else None,
    }

    # ---- human-readable report + verdicts -------------------------------------------------------
    print(f"\nχ-separation phantom diagnostics: {d}\n" + "=" * 64)

    print("\n[1] NULL MODEL  χ± = (χ_total ± R2'/Dr)/2   (closed-form analytic solve)")
    # Judge triviality on NRMSE, not xSIM: the null solve can score high xSIM (structure) yet high
    # NRMSE (magnitude), because white-matter anisotropy shows up in the magnitude error, not the
    # structure. Pick the STRONGEST null attack = the Dr giving the lowest mean detrended NRMSE.
    best = min(report["null_model"], key=lambda r: (r["para_nrmse_detrend"] + r["dia_nrmse_detrend"]))
    for r in report["null_model"]:
        print(f"    Dr={r['dr']:6.1f}  xSIM(para/dia)={r['para_xsim']:.3f}/{r['dia_xsim']:.3f}"
              f"   detr.NRMSE(para/dia)={r['para_nrmse_detrend']:5.1f}/{r['dia_nrmse_detrend']:5.1f}%")
    best_ndt = (best["para_nrmse_detrend"] + best["dia_nrmse_detrend"]) / 2.0
    trivial = best_ndt < 15.0  # analytic solve near-exact -> the board can't measure separation skill
    print(f"    -> best null attack Dr={best['dr']:.0f}: mean detrended NRMSE={best_ndt:.1f}%  "
          f"(xSIM {(best['para_xsim'] + best['dia_xsim']) / 2:.3f}, which is too lenient to judge by).")
    print(f"       {'TRIVIAL: the closed-form solve is near-exact; the board would measure who reproduces it.' if trivial else 'OK: a method must beat this NRMSE to show real separation skill (its high xSIM does not).'}")

    g = report["degeneracy"]
    print(f"\n[2] DEGENERACY  R2' vs single global Dr·(|χ+|+|χ-|)")
    print(f"    best-fit Dr={g['dr_fit']:.1f} Hz/ppm,  unexplained fraction={g['unexplained_frac']:.3f}")
    degen = g["unexplained_frac"] < 0.05
    print(f"    -> {'DEGENERATE: ' if degen else ''}R2' is "
          f"{'a deterministic function of' if degen else 'not fully explained by'} the sources"
          f"{' (closed-form recoverable).' if degen else '.'}")

    c = report["colocation"]
    print(f"\n[3] CO-LOCATION  min(χ+, |χ-|)   (the cancellation regime)")
    print(f"    max={c['max_ppm']:.3f} ppm   " +
          "  ".join(f"{k}:{v*100:.2f}%" for k, v in c["coverage"].items()))
    starved = c["coverage"].get(">0.03ppm", 0.0) < 0.02  # <2% of voxels with both sources sizable
    print(f"    -> {'STARVED: ' if starved else ''}"
          f"{'no' if starved else 'some'} co-located sources; signal-domain separation "
          f"{'cannot' if starved else 'may'} add over a field-domain shortcut.")

    m = report["multicompartment"]
    if m is not None:
        print(f"\n[4] MULTI-COMPARTMENT SIGNATURE  (mono-exp residual vs source content)")
        print(f"    residual median={m['resid_median']:.4f}   corr_with_source={m['corr_with_source']:.3f}")
        inert = abs(m["corr_with_source"]) < 0.2
        print(f"    -> {'INERT: ' if inert else ''}the magnitude "
              f"{'carries no' if inert else 'carries'} separable multi-compartment structure.")
    else:
        print("\n[4] MULTI-COMPARTMENT SIGNATURE  (skipped: no 4D magnitude / TE)")

    print("\n" + "=" * 64)
    print("A discriminating phantom wants: null-model NRMSE HIGH (xSIM is too lenient to judge by),")
    print("degeneracy HIGH unexplained, co-location PRESENT, and (if signal-domain) a multi-comp signature.\n")

    if args.json:
        args.json.write_text(json.dumps(report, indent=2) + "\n")
        print(f"wrote {args.json}")


if __name__ == "__main__":
    main()
