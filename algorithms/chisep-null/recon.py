#!/usr/bin/env python3
"""chisep-null — the closed-form analytic null baseline for χ-separation.

Solves the two source-model equations that define the benchmark's forward model,

    χ+  +  χ-  =  χ_total                (χ- signed, <= 0)
    Dr+·χ+  +  Dr-·|χ-|  =  R2'

exactly, per voxel, from the two provided inputs (χ_total and R2'). No dipole
inversion, no regularisation, no learning — a few array operations. On an
isotropic single-kernel phantom this inverts the phantom's own arithmetic and is
EXACT; on a phantom whose white-matter R2' carries mechanistic (multi-compartment,
orientation-dependent) physics it is not. Its score is therefore the benchmark's
honest floor: any real method must beat it to demonstrate separation skill.

Relaxivity assumptions (stated, field-scaled from the literature):
    Dr+ = 137 * (B0 / 3) Hz/ppm   (Shin et al. 2021 empirical calibration,
                                   scaled linearly with field)
    Dr- = (133.77 / 107.84) * Dr+ (the static-dephasing cylinder/sphere ratio,
                                   Yablonskiy & Haacke 1994)

Usage: recon.py <input-dir> <output-dir>
Consumes: chimap.nii.gz (ppm), r2prime.nii.gz (Hz), mask.nii.gz, params.json (B0)
Produces: chi-para.nii.gz (χ+ >= 0), chi-dia.nii.gz (|χ-| >= 0)
"""
import json
import sys
from pathlib import Path

import numpy as np
import nibabel as nib

DR_POS_3T = 137.0            # Hz/ppm, empirical single-kernel calibration at 3 T
DR_RATIO = 133.77 / 107.84   # cylindrical vs spherical static-dephasing kernels


def main() -> None:
    inp, out = Path(sys.argv[1]), Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)

    params = json.loads((inp / "params.json").read_text())
    b0 = float(params.get("B0", 3.0))
    dr_pos = DR_POS_3T * (b0 / 3.0)
    dr_neg = DR_RATIO * dr_pos

    chi_nii = nib.load(str(inp / "chimap.nii.gz"))
    chi = np.nan_to_num(chi_nii.get_fdata())
    r2p = np.clip(np.nan_to_num(nib.load(str(inp / "r2prime.nii.gz")).get_fdata()), 0, None)
    mask = nib.load(str(inp / "mask.nii.gz")).get_fdata() > 0

    # Exact two-kernel solve of the linear system above (chi- signed negative):
    #   chi+ = (Dr-*chi_total + R2') / (Dr+ + Dr-),  chi- = chi_total - chi+
    pos = (dr_neg * chi + r2p) / (dr_pos + dr_neg)
    neg_signed = chi - pos
    pos = np.clip(pos, 0, None) * mask
    dia = np.clip(-neg_signed, 0, None) * mask

    for name, data in (("chi-para", pos), ("chi-dia", dia)):
        nib.save(nib.Nifti1Image(data.astype(np.float32), chi_nii.affine, chi_nii.header),
                 str(out / f"{name}.nii.gz"))
    print(f"chisep-null: B0={b0} T, Dr+={dr_pos:.1f}, Dr-={dr_neg:.1f} Hz/ppm -> chi-para/chi-dia")


if __name__ == "__main__":
    main()
