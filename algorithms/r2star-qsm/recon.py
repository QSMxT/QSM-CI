#!/usr/bin/env python3
"""R2*-QSM — susceptibility source separation from gradient-echo data (Dimov et al. 2022).

Dimov et al. ("Magnetic Susceptibility Source Separation Solely from Gradient Echo Data",
Tomography 2022; J Neuroimaging 2022, doi:10.1111/jon.13014) separate paramagnetic (χ+, iron)
and diamagnetic (χ−, myelin) susceptibility from GRE data alone — R2* from the multi-echo
magnitude plus a QSM (χ_total) from the phase — with NO separate R2/R2' measurement. The model,
per voxel, is

    R2*  =  𝓇·(|χ+| + |χ−|)          (a single relaxometric constant for both sources)
    χ_total = χ+ + χ−                 (χ+ ≥ 0, χ− ≤ 0)

which inverts in closed form to

    χ+  = (χ_total + R2*/𝓇) / 2 ,   |χ−| = (R2*/𝓇 − χ_total) / 2

with the physical constraints χ+ ≥ 0, |χ−| ≥ 0 enforced by clipping (the paper's voxel-level
initialisation and physical-constraint reset). This is R2*-QSM's core; the full method adds a
field data-consistency term (auto-satisfied here — we take the provided χ_total) and an
edge-masked L1 regularisation that this reference implementation omits.

Relaxometric constant. Dimov calibrated 𝓇 = 274 Hz/ppm at 3 T (a single value for both sources,
"close to the theoretic 321 Hz/ppm"). R2* susceptibility-induced decay scales linearly with B0
while χ does not, so applying the method at the acquisition field uses 𝓇 = 274·(B0/3) Hz/ppm —
the method's own assumption, not retuned to this phantom (its mismatch with the phantom's Dr is a
real, informative model error).

Inputs  (QSM-CI χ-separation contract; a subset): magnitude.nii.gz (4D multi-echo GRE),
        chimap.nii.gz (χ_total, ppm), mask.nii.gz, params.json (TE list in s, B0 in T).
Outputs: chi-para.nii.gz (χ+ ≥ 0), chi-dia.nii.gz (|χ−| ≥ 0, positive magnitude).

Usage: recon.py <input-dir> <output-dir>
"""
import json
import sys
from pathlib import Path

import numpy as np
import nibabel as nib

R_CONST_3T = 274.0   # Hz/ppm, Dimov et al. 2022 empirical relaxometric constant (both sources)


def fit_r2star(mag, tes):
    """R2* (Hz) by weighted log-linear least squares over echoes (mag: X,Y,Z,E; tes: E, seconds).
    Magnitude-weighted so noisy late echoes don't dominate; a robust stand-in for the paper's ARLO."""
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


def main() -> None:
    inp, out = Path(sys.argv[1]), Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)

    p = json.loads((inp / "params.json").read_text())
    b0 = float(p.get("B0", 3.0))
    tes = np.asarray(p["TE"], np.float64)          # seconds
    r = R_CONST_3T * (b0 / 3.0)                     # field-scaled relaxometric constant (Hz/ppm)

    chi_nii = nib.load(str(inp / "chimap.nii.gz"))
    chi = np.nan_to_num(chi_nii.get_fdata())
    mask = nib.load(str(inp / "mask.nii.gz")).get_fdata() > 0
    mag = np.nan_to_num(nib.load(str(inp / "magnitude.nii.gz")).get_fdata())
    if mag.ndim != 4 or mag.shape[-1] != len(tes):
        raise SystemExit(f"magnitude {mag.shape} inconsistent with {len(tes)} TEs")

    r2s = fit_r2star(mag, tes)                      # R2* (Hz) from the multi-echo magnitude
    s = r2s / r                                     # R2*/𝓇 (ppm) = |χ+| + |χ−|
    pos = np.clip((chi + s) / 2.0, 0, None) * mask  # χ+  = (χ_total + R2*/𝓇)/2
    dia = np.clip((s - chi) / 2.0, 0, None) * mask  # |χ−| = (R2*/𝓇 − χ_total)/2

    for name, data in (("chi-para", pos), ("chi-dia", dia)):
        nib.save(nib.Nifti1Image(data.astype(np.float32), chi_nii.affine, chi_nii.header),
                 str(out / f"{name}.nii.gz"))
    print(f"r2star-qsm: B0={b0} T, 𝓇={r:.1f} Hz/ppm, R2* mean {r2s[mask].mean():.1f} Hz "
          f"-> chi-para/chi-dia")


if __name__ == "__main__":
    main()
