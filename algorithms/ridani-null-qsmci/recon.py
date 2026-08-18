#!/usr/bin/env python3
"""ridani-null — the closed-form analytic null baseline for the Ridani et al. phantom family.

Where chisep-null inverts the co-located single-kernel model (Dr+ and Dr- act in every
voxel), ridani-null inverts the *region-disjoint, theoretical field-scaled* model that the
Ridani et al. (2026) phantom is actually built from (calculate_Dr.m / generate_dr_maps_ridani):

    * Paramagnetic relaxivity (spheres), applied OUTSIDE white matter only:
          Dr+ = (2*pi)^2 * gamma_bar * B0 / (9*sqrt(3))   ~= 107.84 * B0  Hz/ppm
    * Diamagnetic relaxivity (parallel cylinders), applied INSIDE white matter only:
          Dr-(theta) = 0.5 * gamma_bar * 2*pi * B0 * sin^2(theta)  ~= 133.77 * B0 * sin^2(theta)
      with the isotropic constant Dr- = 700.8 * (B0/7) used when no fibre-orientation input
      is provided (the reference's constant-Dr option).

so the source-model equations are solved with a DIFFERENT closed form per region:

    outside WM (R2' = Dr+ |chi+|):   chi+ = R2'/Dr+ ,   |chi-| = chi+ - chi_total
    inside  WM (R2' = Dr- |chi-|):   |chi-| = R2'/Dr- ,  chi+ = chi_total + |chi-|

The white-matter region is taken from the provided segmentation (dseg, label 8). This is the
one held-out map ridani-null is granted, exactly so that it can invert the phantom's own
region-disjoint arithmetic: on the isotropic phantom it is EXACT; on the anisotropic phantom,
lacking per-voxel theta, it must assume a constant Dr- in WM and so mis-estimates WM chi- by
the orientation modulation — that residual IS the anisotropy signal the benchmark measures.
Its score is the honest floor for this dataset family: a real method demonstrates skill only by
beating it *without* the segmentation.

If no segmentation is provided at all, ridani-null falls back to the co-located
two-kernel solve (identical in form to chisep-null) so it never crashes on a non-Ridani dataset.

Usage: recon.py <input-dir> <output-dir>
Consumes: chimap.nii.gz (ppm), r2prime.nii.gz (Hz), mask.nii.gz, params.json (B0);
          dseg.nii.gz (segmentation, WM=8) if present.
Produces: chi-para.nii.gz (chi+ >= 0), chi-dia.nii.gz (|chi-| >= 0)
"""
import json
import sys
from pathlib import Path

import numpy as np
import nibabel as nib

GAMMA_BAR = 42.58     # MHz/T, used in the reference's Dr constants
WM_LABEL = 8          # white-matter label in SegmentedModel / dseg
DR_NEG_CONST_7T = 700.8   # Hz/ppm, the reference's constant-Dr- option at 7 T


def _load(p):
    return np.nan_to_num(nib.load(str(p)).get_fdata())


def main() -> None:
    inp, out = Path(sys.argv[1]), Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)

    params = json.loads((inp / "params.json").read_text())
    b0 = float(params.get("B0", 7.0))
    dr_pos = (2 * np.pi) ** 2 * GAMMA_BAR * b0 / (9 * np.sqrt(3))   # ~107.84*B0

    chi_nii = nib.load(str(inp / "chimap.nii.gz"))
    chi = np.nan_to_num(chi_nii.get_fdata())
    r2p = np.clip(_load(inp / "r2prime.nii.gz"), 0, None)
    mask = _load(inp / "mask.nii.gz") > 0

    seg_path = inp / "dseg.nii.gz"
    if seg_path.exists():
        seg = np.round(_load(seg_path)).astype(int)
        wm = seg == WM_LABEL

        # Diamagnetic relaxivity in WM: the reference's field-scaled constant. Orientation is
        # deliberately not available as an input, so WM chi- carries the unmodelled anisotropy
        # residual the benchmark measures.
        dr_neg = np.full_like(chi, DR_NEG_CONST_7T * (b0 / 7.0))
        dr_mode = f"constant Dr- = {DR_NEG_CONST_7T * b0 / 7.0:.1f} Hz/ppm"

        dr_neg_wm = np.where(dr_neg > 0, dr_neg, 1.0)
        # Region-disjoint closed form (chi- signed <= 0):
        pos_out = r2p / dr_pos                     # outside WM: chi+ = R2'/Dr+
        dia_wm = r2p / dr_neg_wm                   # inside  WM: |chi-| = R2'/Dr-
        pos = np.where(wm, chi + dia_wm, pos_out)
        dia = np.where(wm, dia_wm, pos_out - chi)
        mode = f"region-disjoint (WM from dseg, {int(wm.sum())} vox; {dr_mode})"
    else:
        # No segmentation: co-located two-kernel fallback (identical in form to chisep-null),
        # using the theoretical field-scaled cylinder/sphere ratio for Dr-.
        dr_neg = (133.77 / 107.84) * dr_pos
        pos = (dr_neg * chi + r2p) / (dr_pos + dr_neg)
        dia = -(chi - pos)
        mode = "co-located fallback (no dseg)"

    pos = np.clip(pos, 0, None) * mask
    dia = np.clip(dia, 0, None) * mask
    for name, data in (("chi-para", pos), ("chi-dia", dia)):
        nib.save(nib.Nifti1Image(data.astype(np.float32), chi_nii.affine, chi_nii.header),
                 str(out / f"{name}.nii.gz"))
    print(f"ridani-null: B0={b0} T, Dr+={dr_pos:.1f} Hz/ppm, {mode} -> chi-para/chi-dia")


if __name__ == "__main__":
    main()
