#!/usr/bin/env python3
"""check_r2prime_consistency — is the shipped R2' ground truth consistent with the shipped signal?

Fits R2* from the multi-echo GRE magnitude and R2 from the multi-echo SE magnitude
(log-linear mono-exponential fits), derives R2' = clip(R2* - R2, 0), and correlates it
against the shipped inputs/r2prime.nii.gz within the brain mask and within WM (dseg==8).

A low correlation (~0.24 on the 2026-08 phantom) indicates the GT/signal PSF mismatch
(GT image-space-resized, signal k-space-cropped); a consistent phantom should sit near
the noise-limited ceiling (~0.95+ at peak SNR 100, cf. QSM.rs SNR sweep).

Usage:
  python scripts/check_r2prime_consistency.py data/sim/chisep
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import nibabel as nib


def fit_r2_loglin(mag4d: np.ndarray, tes: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Voxel-wise mono-exponential rate via log-linear least squares: ln S = ln S0 - TE*R."""
    eps = 1e-12
    logs = np.log(np.maximum(mag4d, eps))
    t = tes - tes.mean()
    denom = (t ** 2).sum()
    slope = np.tensordot(logs, t, axes=([3], [0])) / denom
    r = -slope
    r[~mask] = 0.0
    return r.astype(np.float32)


def corr(a: np.ndarray, b: np.ndarray, m: np.ndarray) -> float:
    x, y = a[m], b[m]
    if x.size < 10 or x.std() == 0 or y.std() == 0:
        return float("nan")
    return float(np.corrcoef(x, y)[0, 1])


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dataset", type=Path, help="dataset dir with inputs/ (magnitude, se_magnitude, r2prime, mask, params.json)")
    ap.add_argument("--wm-label", type=int, default=8, help="WM label in groundtruth/dseg (default 8)")
    args = ap.parse_args()

    inp = args.dataset / "inputs"
    params = json.loads((inp / "params.json").read_text())
    tes = np.asarray(params["TE"], float)
    se_tes = np.asarray(params["se_TE"], float)

    mag = nib.load(str(inp / "magnitude.nii.gz")).get_fdata()
    se = nib.load(str(inp / "se_magnitude.nii.gz")).get_fdata()
    r2p_gt = nib.load(str(inp / "r2prime.nii.gz")).get_fdata()
    mask = nib.load(str(inp / "mask.nii.gz")).get_fdata() > 0

    r2star = fit_r2_loglin(mag, tes, mask)
    r2 = fit_r2_loglin(se, se_tes, mask)
    r2p = np.clip(r2star - r2, 0, None)

    print(f"dataset: {args.dataset}")
    print(f"  GRE TEs (ms): {(tes * 1e3).astype(int).tolist()}   SE TEs (ms): {(se_tes * 1e3).astype(int).tolist()}")
    print(f"  brain: R2* mean {r2star[mask].mean():6.2f} Hz | R2 mean {r2[mask].mean():6.2f} Hz | "
          f"R2' fit mean {r2p[mask].mean():5.2f} Hz vs GT {r2p_gt[mask].mean():5.2f} Hz")
    print(f"  corr(R2'_fit, R2'_GT) brain = {corr(r2p, r2p_gt, mask):+.3f}")

    dseg_p = args.dataset / "groundtruth" / "dseg.nii.gz"
    if dseg_p.exists():
        dseg = nib.load(str(dseg_p)).get_fdata()
        wm = mask & (dseg == args.wm_label)
        print(f"  corr(R2'_fit, R2'_GT) WM(dseg=={args.wm_label}, n={int(wm.sum())}) = {corr(r2p, r2p_gt, wm):+.3f}")


if __name__ == "__main__":
    main()
