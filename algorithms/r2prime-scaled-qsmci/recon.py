#!/usr/bin/env python3
"""r2prime-scaled — the fixed-fraction R2′-from-R2* heuristic (QSM-CI `r2prime-generation` stage).

When no spin-echo acquisition provides a measured R2 (the GRE-only condition), the common fallback
is a fixed linear scaling of R2*: R2′ ≈ f·R2*, with f = 0.52 the literature value (attributed to
Dimov et al.; evaluated as "R2′ = 0.52 × R2*" in Ji et al., NMR Biomed 2024, doi:10.1002/nbm.5167,
and Oliveira Assunção et al., Magn Reson Med 2026, doi:10.1002/mrm.30238 — both of which document
the substantial χ-separation error this heuristic can propagate, which is exactly what this
generator lets the benchmark measure). R2* is fit from the multi-echo GRE magnitude by weighted
log-linear least squares (the same robust ARLO stand-in as the r2star-qsm submission).

Inputs  (QSM-CI r2prime-generation contract): magnitude.nii.gz (4D multi-echo GRE),
        mask.nii.gz, params.json (TE list in s).
Output: r2prime.nii.gz (Hz).

Usage: recon.py <input-dir> <output-dir>
"""
import json
import sys
from pathlib import Path

import numpy as np
import nibabel as nib

DEFAULT_FRACTION = 0.52   # literature R2'/R2* scaling (see module docstring)


def fit_r2star(mag, tes):
    """R2* (Hz) by weighted log-linear least squares over echoes (mag: X,Y,Z,E; tes: E, seconds).
    Magnitude-weighted so noisy late echoes don't dominate; a robust stand-in for ARLO."""
    mag = np.clip(np.asarray(mag, np.float64), 1e-9, None)
    t = np.asarray(tes, np.float64)
    w = mag ** 2                                   # weight ∝ magnitude² (SNR)
    logm = np.log(mag)
    sw = w.sum(-1)
    tbar = (w * t).sum(-1) / sw
    lbar = (w * logm).sum(-1) / sw
    cov = (w * (t - tbar[..., None]) * (logm - lbar[..., None])).sum(-1)
    var = (w * (t - tbar[..., None]) ** 2).sum(-1)
    slope = np.divide(cov, var, out=np.zeros_like(cov), where=var > 0)
    return np.clip(-slope, 0, None)                # R2* = −slope of log-magnitude vs TE


def read_fraction(inp: Path) -> float:
    """R2'/R2* fraction, overridable via `qsm-ci run r2prime-scaled-qsmci --set fraction=...`
    (arrives as <input>/config.json), else the literature default 0.52."""
    p = inp / "config.json"
    if p.exists():
        v = json.loads(p.read_text()).get("fraction")
        if v is not None:
            return float(v)
    return DEFAULT_FRACTION


def main() -> None:
    inp, out = Path(sys.argv[1]), Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)

    p = json.loads((inp / "params.json").read_text())
    tes = np.asarray(p["TE"], np.float64)          # seconds
    frac = read_fraction(inp)

    mag_nii = nib.load(str(inp / "magnitude.nii.gz"))
    mag = np.nan_to_num(mag_nii.get_fdata())
    mask = nib.load(str(inp / "mask.nii.gz")).get_fdata() > 0
    if mag.ndim != 4 or mag.shape[-1] != len(tes):
        raise SystemExit(f"magnitude {mag.shape} inconsistent with {len(tes)} TEs")

    r2s = fit_r2star(mag, tes)
    r2p = (frac * r2s * mask).astype(np.float32)
    nib.save(nib.Nifti1Image(r2p, mag_nii.affine, mag_nii.header), str(out / "r2prime.nii.gz"))
    print(f"r2prime-scaled: fraction={frac}, R2* mean {r2s[mask].mean():.1f} Hz "
          f"-> R2' mean {r2p[mask].mean():.1f} Hz")


if __name__ == "__main__":
    main()
