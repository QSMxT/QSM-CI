#!/usr/bin/env python3
"""gen_chisep — reproducible generator for the χ-separation phantom (data/sim/chisep).

Implements the susceptibility source-separation phantom of Ridani et al. (2026) [1] on the
QSM Reconstruction Challenge 2.0 head model [2]. χ+/χ- are constructed per tissue from literature
susceptibility values with R1/R2*-driven intra-tissue modulation, and χ- carries orientation-dependent
white-matter anisotropy (χ- = Δχ·cos²θ + χ0, θ = fibre-to-B0 angle from the diffusion V1 eigenvector).
χ_total = χ+ + χ- is the shipped susceptibility map and drives the simulated field and multi-echo GRE
signal. Acquisition: 7 T, 4 echoes [4,12,20,28] ms, 1 mm, peak SNR 100, seed 42.

Susceptibility-to-R2' relaxivity (Dr) magnitude, selected with --dr-model (both keep the same
orientation-dependent sin^2(theta) shape for Dr-; they differ only in absolute magnitude):
  fixed (default): paramagnetic relaxivity anchored at Dr+ = 137 Hz/ppm (Shin et al. 2021 [3]),
      field-independent; the diamagnetic relaxivity is scaled by the same factor. Produces R2'
      magnitudes consistent with in-vivo χ-separation calibrations at any field strength.
  scaled: magnitude from the static-dephasing model (Yablonskiy & Haacke 1994 [4]) as used in [1] —
      Dr+ = 2πγB0/(9√3) for spherical sources, Dr- = ½γB0·sin²θ for cylindrical sources — which scales
      linearly with field (Dr+ = 107.84·B0, Dr- = 133.77·sin²θ·B0 Hz/ppm).
The χ+/χ- ground truth is identical for both; only R2' and the signal decay scale differ.
--isotropic disables anisotropy (spatially constant Dr- = 700.8 Hz/ppm).

Required inputs in the qsm-forward data dir:
  chimodel/, maps/{R1,R2star,M0,V1}, masks/{SegmentedModel,BrainMask,highgrad,white_matter_mask},
  raw/rawField.nii.gz (total field, used for the intra-tissue two-model weighting).

The χ+/χ- construction wavelet-denoises R1/R2* (~5 min) and the field/signal simulation needs several
GB of RAM; run the full path on a compute node.

  [1] Ridani S., De Leener B., Alonso-Ortiz E. bioRxiv 2026. doi:10.64898/2026.04.07.716972
  [2] Marques J.P. et al. Magn Reson Med 2021;86(1):526-542. doi:10.1002/mrm.28716
  [3] Shin H.G. et al. NeuroImage 2021;240:118371. doi:10.1016/j.neuroimage.2021.118371
  [4] Yablonskiy D.A., Haacke E.M. Magn Reson Med 1994;32(6):749-763. doi:10.1002/mrm.1910320610

Usage (qsm-forward venv):
  python scripts/gen_chisep.py --maps-only --validate                        # cheap χ+/χ-/R2' check
  python scripts/gen_chisep.py --out data/sim/chisep                         # full sim (compute node)
  python scripts/gen_chisep.py --dr-model scaled --out data/sim/chisep-scaled
  python scripts/gen_chisep.py --isotropic --out data/sim/chisep-isotropic
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import nibabel as nib

SEED = 42
B0 = 7.0
B0_DIR = np.array([0.0, 0.0, 1.0])
TES = np.array([0.004, 0.012, 0.020, 0.028])
VOXEL = np.array([1.0, 1.0, 1.0])
PEAK_SNR = 100.0
DR_FIXED_POS = 137.0  # Hz/ppm, paramagnetic relaxivity (Shin et al. 2021)
SE_TR = 1.5           # s, spin-echo repetition time
SE_TES = np.array([0.010, 0.030, 0.050, 0.070])  # s, multi-echo spin-echo (magnitude decays with R2)


def mask_derived_to_brain(out: Path):
    """Restrict the derived maps and ground truth to the brain, leaving the raw
    phase/magnitude (which carry the whole-head background field) untouched."""
    m = nib.load(str(out / "inputs" / "mask.nii.gz")).get_fdata() > 0
    for rel in ("inputs/chimap.nii.gz", "inputs/r2prime.nii.gz", "inputs/localfield.nii.gz",
                "groundtruth/chi-para.nii.gz", "groundtruth/chi-dia.nii.gz", "groundtruth/chimap.nii.gz"):
        p = out / rel
        if p.exists():
            im = nib.load(str(p))
            nib.save(nib.Nifti1Image((im.get_fdata() * m).astype(np.float32), im.affine, im.header), str(p))


def write_maps_dataset(out: Path, chi_total, r2prime, mask, chi_pos, chi_neg, affine, header):
    def save(rel, data):
        p = out / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        nib.save(nib.Nifti1Image(np.asarray(data, np.float32), affine, header), str(p))
    save("inputs/chimap.nii.gz", chi_total)
    save("inputs/r2prime.nii.gz", r2prime)
    save("inputs/mask.nii.gz", mask.astype(np.float32))
    save("groundtruth/chi-para.nii.gz", chi_pos)
    save("groundtruth/chi-dia.nii.gz", np.abs(chi_neg))


def write_fiber_angle(out: Path, v1, b0_dir, affine, header, out_shape, brain_mask):
    """Write inputs/fiber_angle.nii.gz — the fibre-to-B0 angle (degrees) from the diffusion V1
    eigenvector, resampled to the dataset grid and brain-masked. This is the orientation information a
    real DTI acquisition provides; an anisotropy-aware χ-separation method can use it (D_r-(θ) ∝ sin²θ)
    to recover white-matter χ-, which a single-orientation isotropic method cannot. An OPTIONAL input:
    only physically meaningful in white matter (~0 elsewhere)."""
    from scipy.ndimage import zoom
    b0 = np.asarray(b0_dir, float); b0 = b0 / (np.linalg.norm(b0) + 1e-12)
    norm = np.linalg.norm(v1, axis=-1)
    cos = np.abs((v1 * b0).sum(-1)) / np.where(norm > 1e-6, norm, 1.0)
    ang = np.degrees(np.arccos(np.clip(cos, 0.0, 1.0))).astype(np.float32)
    ang[norm <= 1e-6] = 0.0
    if ang.shape != tuple(out_shape):
        ang = zoom(ang, [out_shape[i] / ang.shape[i] for i in range(3)], order=1).astype(np.float32)
    ang *= (brain_mask > 0)
    p = out / "inputs" / "fiber_angle.nii.gz"
    p.parent.mkdir(parents=True, exist_ok=True)
    nib.save(nib.Nifti1Image(ang, affine, header), str(p))
    print(f"  wrote {p.name} (fibre-to-B0 angle in deg; optional WM-anisotropy input)")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--qsmf-data", type=Path, default=Path.home() / "repos/qsm/qsm-forward/data")
    ap.add_argument("--out", type=Path, default=Path("data/sim/chisep"))
    ap.add_argument("--bids", type=Path, default=Path("/tmp/chisep_bids"))
    ap.add_argument("--isotropic", action="store_true",
                    help="disable WM anisotropy (spatially constant Dr- = 700.8 Hz/ppm)")
    ap.add_argument("--full-head", action="store_true",
                    help="also ship the derived maps (chimap, R2', local field) and ground truth over the "
                         "whole head; by default these are masked to the brain while the raw phase/magnitude "
                         "keep the whole-head background field")
    ap.add_argument("--dr-model", choices=["fixed", "scaled"], default="fixed",
                    help="Dr relaxivity magnitude (default: fixed, Dr+ = 137 Hz/ppm, field-independent; "
                         "scaled: static-dephasing Dr+ = 107.84*B0, Dr- = 133.77*sin^2(theta)*B0)")
    ap.add_argument("--maps-only", action="store_true", help="only build χ+/χ-/R2' (+ maps dataset), no sim")
    ap.add_argument("--validate", action="store_true", help="run validate_phantom.py on the written dataset")
    args = ap.parse_args()

    try:
        import qsm_forward as q
    except ModuleNotFoundError:
        sys.exit("import qsm_forward failed — run with the qsm-forward venv python.")

    aniso = not args.isotropic
    data = str(args.qsmf_data)
    print(f"Building χ+/χ- (anisotropy={aniso})...")
    # Build whole-head χ so the simulated field/signal carry the background field; the derived maps
    # and ground truth are masked to the brain after packing (unless --full-head).
    tp = q.TissueParams(root_dir=data, chisep_anisotropy=aniso, chisep_apply_brain_mask=False)
    chi_pos = tp.chi_pos.get_fdata().astype(np.float32)
    chi_neg = tp.chi_neg.get_fdata().astype(np.float32)
    chi_total = (chi_pos + chi_neg).astype(np.float32)
    seg = tp.seg.get_fdata()
    mask = tp.mask.get_fdata() > 0

    # Orientation-dependent relaxivity maps (Dr+ spherical, Dr- cylindrical sin^2(theta)).
    # dr_fixed anchors Dr+ at 137 Hz/ppm (field-independent); None keeps the field-scaled magnitudes.
    theta = q.generate_theta_from_v1(tp.v1.get_fdata(), B0_DIR) if tp.v1 is not None else None
    dr_fixed = DR_FIXED_POS if args.dr_model == "fixed" else None
    dr_pos_map, dr_neg_map = q.generate_dr_maps_ridani(seg, theta, B0=B0, anisotropic=aniso, dr_fixed=dr_fixed)
    print(f"  Dr model={args.dr_model}: Dr+ = {dr_pos_map[dr_pos_map > 0].mean():.1f} Hz/ppm")
    r2prime = q.generate_r2prime(chi_pos, chi_neg, dr=dr_pos_map, dr_neg=dr_neg_map)

    coloc = np.minimum(np.abs(chi_pos), np.abs(chi_neg))[mask].max()
    print(f"  χ+ max={np.abs(chi_pos).max():.3f}  |χ-| max={np.abs(chi_neg).max():.3f}  "
          f"R2' max={r2prime.max():.1f} Hz  co-loc max={coloc:.3f} ppm")

    if args.maps_only:
        b = 1.0 if args.full_head else mask.astype(np.float32)
        write_maps_dataset(args.out, chi_total * b, r2prime * b, mask,
                           chi_pos * b, chi_neg * b, tp.nii_affine, tp.nii_header)
        if aniso and tp.v1 is not None:
            write_fiber_angle(args.out, tp.v1.get_fdata(), B0_DIR, tp.nii_affine, tp.nii_header,
                              mask.shape, (mask if args.full_head else mask).astype(np.float32))
        print(f"--maps-only: wrote maps dataset to {args.out} (no field/signal sim).")
    else:
        print("Simulating field + χ-separation GRE signal...")
        # Write the built maps to files carrying the base 0.64 mm header/affine, so generate_bids
        # downsamples to the requested voxel size (passing bare arrays would lose the zoom and skip it).
        tmpd = tempfile.mkdtemp()
        def _w(name, arr):
            p = str(Path(tmpd) / name)
            nib.save(nib.Nifti1Image(arr.astype(np.float32), tp.nii_affine, tp.nii_header), p)
            return p
        tp2 = q.TissueParams(root_dir=data,
                             chi=_w("chi.nii.gz", chi_total),
                             chi_pos=_w("chi_pos.nii.gz", chi_pos),
                             chi_neg=_w("chi_neg.nii.gz", chi_neg))
        rp = q.ReconParams(subject="1", B0=B0, TEs=TES, voxel_size=VOXEL, peak_snr=PEAK_SNR,
                           random_seed=SEED, se_TR=SE_TR, se_TEs=SE_TES)
        q.generate_bids(
            tp2, rp, str(args.bids),
            save_field=True, save_chi_pos=True, save_chi_neg=True, save_r2prime=True,
            dr_pos_map=dr_pos_map, dr_neg_map=dr_neg_map, dr=DR_FIXED_POS,
            chisep_signal=True, chisep_multicompartment=False, save_se=True,
        )
        pack = Path(__file__).with_name("pack_dataset.py")
        print(f"Packing {args.bids} -> {args.out} ...")
        subprocess.run([sys.executable, str(pack), str(args.bids), str(args.out), "--chisep"], check=True)
        if not args.full_head:
            mask_derived_to_brain(args.out)
            print("Masked derived maps + ground truth to the brain (raw phase/magnitude kept whole-head).")
        if aniso and tp.v1 is not None:  # optional DTI-orientation input, on the packed (downsampled) grid
            mimg = nib.load(str(args.out / "inputs" / "mask.nii.gz"))
            write_fiber_angle(args.out, tp.v1.get_fdata(), B0_DIR, mimg.affine, mimg.header,
                              mimg.shape, mimg.get_fdata())
        print("Done. Re-score methods after regenerating.")

    if args.validate:
        v = Path(__file__).with_name("validate_phantom.py")
        subprocess.run([sys.executable, str(v), str(args.out)], check=True)


if __name__ == "__main__":
    main()
