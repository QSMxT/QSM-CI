#!/usr/bin/env python3
"""gen_chisep — reproducible generator for the χ-separation phantom (data/sim/chisep).

Implements the susceptibility source-separation phantom of Ridani et al. (2026) [1] on the
QSM Reconstruction Challenge 2.0 head model [2]. χ+/χ- are constructed per tissue from literature
susceptibility values with R1/R2*-driven intra-tissue modulation, and χ- carries orientation-dependent
white-matter anisotropy (χ- = Δχ·cos²θ + χ0, θ = fibre-to-B0 angle from the diffusion V1 eigenvector).
χ_total = χ+ + χ- is the shipped susceptibility map and drives the simulated field and multi-echo GRE
signal. Acquisition: 7 T, 4 echoes [4,12,20,28] ms, 1 mm, peak SNR 100, seed 42.

DEFAULTS REPRODUCE THE RIDANI MODEL: --dr-model scaled (their theoretical kernels), anisotropy on,
their 7T protocol (TR 50 ms, flip 15°, TEs 4/12/20/28 ms), no multicompartment signal, and the
V1 L-A-S→R-A-S flip (which Ridani's published phantom also uses — see V1 ORIENTATION below).
Departures from Ridani-as-published that remain on by default: the matched spin-echo acquisition
(additive data the benchmark needs; the SE model is plain mono-exponential R2 unless
--multicompartment) and the native-resolution packaging.

THE QSM-CI SHIPPING CONFIGURATION is explicit:
  python scripts/gen_chisep.py --multicompartment --dr-model fixed --dr-fixed 320 \
      --tes 3,9,15,21,27,33,39,45 --out data/sim/chisep-ship

Susceptibility-to-R2' relaxivity (Dr) magnitude, selected with --dr-model (both keep the same
orientation-dependent sin^2(theta) shape for Dr-; they differ only in absolute magnitude):
  scaled (default; Ridani's convention): magnitude from the static-dephasing model (Yablonskiy &
      Haacke 1994 [4]) as used in [1] — Dr+ = 2πγB0/(9√3) for spherical sources, Dr- = ½γB0·sin²θ for
      cylindrical sources — which scales linearly with field (Dr+ = 107.84·B0, Dr- = 133.77·sin²θ·B0
      Hz/ppm).
  fixed: paramagnetic relaxivity anchored at --dr-fixed Hz/ppm (default 137, Shin et al. 2021 [3];
      the shipping config uses 320 = 137·(7/3), the field-scaled empirical calibration),
      field-independent in B0; the diamagnetic relaxivity is scaled by the same factor.
The χ+/χ- ground truth is identical for both; only R2' and the signal decay scale differ.
--isotropic disables anisotropy (spatially constant Dr-).

Required inputs in the qsm-forward data dir:
  chimodel/, maps/{R1,R2star,M0,V1}, masks/{SegmentedModel,BrainMask,highgrad,white_matter_mask},
  raw/rawField.nii.gz (total field, used for the intra-tissue two-model weighting).

PSF consistency: the maps are built at the native 0.64 mm (the χ+/χ- texture construction needs the
real R1/R2* maps), then ALL maps are image-space-downsampled ONCE to the scoring resolution and the
field + GRE + SE signals are simulated NATIVELY at that resolution (no k-space crop anywhere). The
ground truth is exactly the maps that generated the signal — the signal-derivable R2' = R2*-R2 matches
the shipped r2prime with corr 1.000 in the noiseless limit (the historical 0.64-mm-sim +
k-space-crop design mismatched the GT/signal PSFs, corr 0.24 — see STATUS.md). Trade-off: the
signal carries no sub-voxel partial-volume content (a scored phantom cannot have both a clean
parameter GT and a realistic sub-voxel PV signal).

The χ+/χ- construction wavelet-denoises R1/R2* (~5 min); the default native-resolution simulation is
light enough to run locally.

  [1] Ridani D., De Leener B., Alonso-Ortiz E. Magn Reson Med 2026. doi:10.1002/mrm.70468
  [2] Marques J.P. et al. Magn Reson Med 2021;86(1):526-542. doi:10.1002/mrm.28716
  [3] Shin H.G. et al. NeuroImage 2021;240:118371. doi:10.1016/j.neuroimage.2021.118371
  [4] Yablonskiy D.A., Haacke E.M. Magn Reson Med 1994;32(6):749-763. doi:10.1002/mrm.1910320610

Usage (qsm-forward venv):
  python scripts/gen_chisep.py --maps-only --validate                        # cheap χ+/χ-/R2' check
  python scripts/gen_chisep.py --out data/sim/chisep                         # full sim (compute node)
  python scripts/gen_chisep.py --dr-model fixed --dr-fixed 320 --out data/sim/chisep-empirical
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
# V1 ORIENTATION. The challenge V1.nii.gz is stored L-A-S — mirrored along the first (x) axis
# relative to every other map (all R-A-S). np.flip(V1, axis=0) registers it; this is what
# Ridani's published phantom used (theta from the flipped V1 reproduces their published theta
# map exactly, max diff 0.0000 deg). No vector-component negation is needed: theta only uses
# squared components. The historical integer shift (+5,+1,-6), chosen by mask overlap, was a
# flip-of-an-off-center-brain in disguise and is retired.
B0_DIR = np.array([0.0, 0.0, 1.0])
TES = np.array([0.004, 0.012, 0.020, 0.028])
VOXEL = np.array([1.0, 1.0, 1.0])
PEAK_SNR = 100.0
DR_FIXED_POS = 137.0  # Hz/ppm, paramagnetic relaxivity (Shin et al. 2021)
SE_TR = 1.5           # s, spin-echo repetition time
SE_TES = np.array([0.010, 0.030, 0.050, 0.070])  # s, multi-echo spin-echo (magnitude decays with R2)

# As-published Ridani et al. (MRM doi:10.1002/mrm.70468) configurations. All three are
# noiseless, GRE-only (no SE; the paper's R2' convention is R2*_fit - R2_GT, so the GT R2
# ships as an input instead) and use the theoretical field-scaled Dr kernels. The default
# V1 flip applies (their phantom used it — see V1 ORIENTATION above).
# 3T protocol: TR 50 ms, FA 15, TE1/dTE/TE6 = 3/4/23 ms; 7T: TE1/dTE/TE4 = 4/8/28 ms.
_RIDANI_COMMON = dict(dr_model="scaled", noiseless=True, no_se=True, r2_input=True, voxel=0.0)
RIDANI_PRESETS = {
    "ridani-3t-iso":   dict(b0=3.0, tes="3,7,11,15,19,23", isotropic=True, **_RIDANI_COMMON),
    "ridani-3t-aniso": dict(b0=3.0, tes="3,7,11,15,19,23", isotropic=False, **_RIDANI_COMMON),
    "ridani-7t-aniso": dict(b0=7.0, tes="4,12,20,28", isotropic=False, **_RIDANI_COMMON),
}


def _ds_theta(theta, ds):
    """Downsample a fibre-angle map whose no-fibre voxels are NaN, by normalized interpolation:
    interpolate the NaN-zeroed values and a validity indicator separately, divide, and mark
    voxels with less than half fibre support as NaN (spline-interpolating NaNs directly is
    ill-defined and leaks them into neighbouring voxels)."""
    valid = np.isfinite(theta).astype(np.float32)
    num = ds(np.nan_to_num(theta).astype(np.float32))
    den = ds(valid)
    out = np.full(num.shape, np.nan, np.float32)
    ok = den > 0.5
    out[ok] = num[ok] / den[ok]
    return out


def mask_derived_to_brain(out: Path):
    """Restrict the derived maps and ground truth to the brain, leaving the raw
    phase/magnitude (which carry the whole-head background field) untouched."""
    m = nib.load(str(out / "inputs" / "mask.nii.gz")).get_fdata() > 0
    for rel in ("inputs/chimap.nii.gz", "inputs/r2prime.nii.gz", "inputs/localfield.nii.gz",
                "inputs/r2.nii.gz",
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
    ap.add_argument("--dr-model", choices=["fixed", "scaled"], default="scaled",
                    help="Dr relaxivity magnitude (default: scaled — Ridani's own convention, the "
                         "theoretical static-dephasing kernels Dr+ = 107.84*B0, Dr- = 133.77*sin^2(theta)*B0 "
                         "Hz/ppm; fixed: anchor Dr+ at --dr-fixed Hz/ppm, field-independent — the "
                         "QSM-CI shipping config uses --dr-model fixed --dr-fixed 320)")
    ap.add_argument("--b0", type=float, default=7.0,
                    help="acquisition field strength in tesla (default 7.0)")
    ap.add_argument("--dr-fixed", type=float, default=DR_FIXED_POS,
                    help="Dr+ anchor for --dr-model fixed, Hz/ppm (default %g = Shin's 3T-empirical "
                         "calibration; the literature-consistent 7T value is ~320 = 137*(7/3), since "
                         "Dr scales linearly with B0)" % DR_FIXED_POS)
    ap.add_argument("--peak-snr", type=float, default=PEAK_SNR,
                    help="peak SNR of the simulated acquisition (default %g)" % PEAK_SNR)
    ap.add_argument("--voxel", type=float, default=1.0,
                    help="isotropic scoring/simulation voxel size in mm (default 1.0); 0 keeps the "
                         "native 0.64 mm grid with no resampling at all (the Ridani presets use this, "
                         "matching the reference's native-resolution data)")
    ap.add_argument("--hc-b0", type=float, default=None,
                    help="effective field strength for the hollow-cylinder pool physics only "
                         "(default: the acquisition --b0). E.g. 1.27 evaluates the mechanistic WM "
                         "dephasing at the field where the physical Dr equals the fixed calibration "
                         "Dr=137. Requires qsm-forward with chisep_hc_b0 support.")
    ap.add_argument("--multicompartment", action="store_true",
                    help="enable the hollow-cylinder 3-pool WM GRE signal (qsm-forward PR #7): θ-dependent "
                         "non-mono-exponential decay makes WM anisotropy recoverable from the signal. "
                         "Native-resolution path only.")
    ap.add_argument("--tes", default=None,
                    help="comma-separated GRE TEs in ms (default: 4,12,20,28); e.g. a denser train for "
                         "the multicompartment myelin-water beat")
    ap.add_argument("--se-tes", default=None,
                    help="comma-separated spin-echo TEs in ms (default: 10,30,50,70)")
    ap.add_argument("--no-v1-flip", action="store_true",
                    help="skip the V1 L-A-S -> R-A-S registration flip (see V1 ORIENTATION); reproduces "
                         "the public PhantomCreation.m behaviour (mirrored fibres) — for comparison only")
    ap.add_argument("--noiseless", action="store_true",
                    help="skip acquisition noise entirely (the Ridani headline configs are noiseless)")
    ap.add_argument("--no-se", action="store_true",
                    help="skip the matched spin-echo acquisition (the Ridani phantom simulates GRE only)")
    ap.add_argument("--wm-rois-src", type=Path, default=None,
                    help="fibre-bundle WM sub-ROI atlas (Ridani OSF 9xwhz Masks/WM_fibers_seg.nii.gz) to "
                         "ship as groundtruth/wm_rois.nii.gz — the label map the χ- per-ROI MSPE averages over")
    ap.add_argument("--r2-input", action="store_true",
                    help="ship the ground-truth R2 map as inputs/r2.nii.gz (the Ridani evaluation "
                         "convention: methods fit R2* from the GRE and use R2' = R2*_fit - R2_GT)")
    ap.add_argument("--preset", choices=sorted(RIDANI_PRESETS),
                    help="as-published Ridani et al. (MRM 10.1002/mrm.70468) configurations: sets B0, "
                         "echo train, iso/aniso, scaled Dr, noiseless, GRE-only + r2 input")
    ap.add_argument("--maps-only", action="store_true", help="only build χ+/χ-/R2' (+ maps dataset), no sim")
    ap.add_argument("--validate", action="store_true", help="run validate_phantom.py on the written dataset")
    args = ap.parse_args()
    if args.preset:
        for k, v in RIDANI_PRESETS[args.preset].items():
            setattr(args, k, v)
        print(f"Preset {args.preset}: B0={args.b0}T TEs={args.tes} isotropic={args.isotropic} "
              f"dr_model={args.dr_model} noiseless, GRE-only (+ inputs/r2)")

    try:
        import qsm_forward as q
    except ModuleNotFoundError:
        sys.exit("import qsm_forward failed — run with the qsm-forward venv python.")

    tes = TES if args.tes is None else np.array([float(t) * 1e-3 for t in args.tes.split(",")])
    se_tes = SE_TES if args.se_tes is None else np.array([float(t) * 1e-3 for t in args.se_tes.split(",")])

    aniso = not args.isotropic
    data = str(args.qsmf_data)
    print(f"Building χ+/χ- (anisotropy={aniso})...")
    # Register V1 to the segmentation (see V1 ORIENTATION) BEFORE it feeds anything — the χ-
    # anisotropy ground truth and theta must use the same registered fibres.
    v1_kw = {}
    if not args.no_v1_flip:
        v1_path = args.qsmf_data / "maps" / "V1.nii.gz"
        if v1_path.exists():
            v1_kw["v1"] = np.flip(nib.load(str(v1_path)).get_fdata().astype(np.float32), axis=0).copy()
            print("  V1 registered to the segmentation: L-A-S -> R-A-S flip along axis 0")
    # Build whole-head χ so the simulated field/signal carry the background field; the derived maps
    # and ground truth are masked to the brain after packing (unless --full-head).
    tp = q.TissueParams(root_dir=data, chisep_anisotropy=aniso, chisep_apply_brain_mask=False, **v1_kw)
    chi_pos = tp.chi_pos.get_fdata().astype(np.float32)
    chi_neg = tp.chi_neg.get_fdata().astype(np.float32)
    chi_total = (chi_pos + chi_neg).astype(np.float32)
    seg = tp.seg.get_fdata()
    mask = tp.mask.get_fdata() > 0

    # Orientation-dependent relaxivity maps (Dr+ spherical, Dr- cylindrical sin^2(theta)).
    # dr_fixed anchors Dr+ at 137 Hz/ppm (field-independent); None keeps the field-scaled magnitudes.
    theta = q.generate_theta_from_v1(tp.v1.get_fdata(), B0_DIR) if tp.v1 is not None else None
    dr_fixed = args.dr_fixed if args.dr_model == "fixed" else None
    dr_pos_map, dr_neg_map = q.generate_dr_maps_ridani(seg, theta, B0=args.b0, anisotropic=aniso, dr_fixed=dr_fixed)
    print(f"  Dr model={args.dr_model}: Dr+ = {dr_pos_map[dr_pos_map > 0].mean():.1f} Hz/ppm")
    r2prime = q.generate_r2prime(chi_pos, chi_neg, dr=dr_pos_map, dr_neg=dr_neg_map)

    coloc = np.minimum(np.abs(chi_pos), np.abs(chi_neg))[mask].max()
    print(f"  χ+ max={np.abs(chi_pos).max():.3f}  |χ-| max={np.abs(chi_neg).max():.3f}  "
          f"R2' max={r2prime.max():.1f} Hz  co-loc max={coloc:.3f} ppm")

    if args.maps_only:
        b = 1.0 if args.full_head else mask.astype(np.float32)
        write_maps_dataset(args.out, chi_total * b, r2prime * b, mask,
                           chi_pos * b, chi_neg * b, tp.nii_affine, tp.nii_header)
        print(f"--maps-only: wrote maps dataset to {args.out} (no field/signal sim).")
    else:
        tmpd = tempfile.mkdtemp()
        # PSF-consistent design: downsample ALL maps to the scoring resolution ONCE (image-space,
        # the same operator the ground truth has always used — the shipped GT is unchanged), then
        # simulate field + signal NATIVELY at that resolution so no k-space crop happens anywhere.
        # Every input and the GT then share a single (identity) PSF: the signal-derived
        # R2' = R2*-R2 matches the shipped r2prime exactly in the noiseless limit (corr 1.000; the
        # historical 0.64-mm-sim + k-space-crop design scored 0.24 — see STATUS.md, removed
        # 2026-08-11), at the cost of sub-voxel partial-volume content in the signal (a scored
        # phantom cannot have both — QSM.rs PSF lessons).
        # --voxel 0 keeps the native grid (no resample at all — the Ridani presets, matching the
        # reference's native-resolution outputs).
        native = args.voxel <= 0
        voxel = np.asarray(tp.voxel_size, float) if native else np.array([args.voxel] * 3, float)
        print("Simulating at the native grid (no resample, no k-space crop)..." if native else
              f"Downsampling maps to {voxel.tolist()} mm and simulating NATIVELY (no k-space crop)...")
        def _ds(arr, interp="continuous"):
            if native:
                return np.asarray(arr, np.float32)
            nii = nib.Nifti1Image(np.asarray(arr, np.float32), tp.nii_affine, tp.nii_header)
            return q.resize(nii, voxel, interp).get_fdata().astype(np.float32)
        chi_pos = _ds(chi_pos)
        chi_neg = _ds(chi_neg)
        chi_total = chi_pos + chi_neg
        dr_pos_sim = _ds(dr_pos_map)
        dr_neg_sim = _ds(dr_neg_map)
        th1 = theta.astype(np.float32) if (theta is not None and native) else (
            _ds_theta(theta, _ds) if theta is not None else None)
        aff1 = tp.nii_affine if native else q.resize(
            nib.Nifti1Image(chi_total, tp.nii_affine, tp.nii_header), voxel).affine
        def _w1(name, arr):
            p = str(Path(tmpd) / name)
            nib.save(nib.Nifti1Image(np.asarray(arr, np.float32), aff1), p)
            return p
        tp2 = q.TissueParams(
            root_dir=data,
            chi=_w1("chi.nii.gz", chi_total),
            chi_pos=_w1("chi_pos.nii.gz", chi_pos),
            chi_neg=_w1("chi_neg.nii.gz", chi_neg),
            mask=_w1("mask.nii.gz", _ds(tp.mask.get_fdata(), "nearest")),
            seg=_w1("seg.nii.gz", _ds(seg, "nearest")),
            M0=_w1("M0.nii.gz", _ds(tp.M0.get_fdata())),
            R1=_w1("R1.nii.gz", _ds(tp.R1.get_fdata())),
            R2star=_w1("R2star.nii.gz", _ds(tp.R2star.get_fdata())),
            # V1-derived fibre-to-B0 angle (degrees) on the 1 mm grid — the hollow-cylinder
            # multicompartment WM signal reads it as tissue_params.angle_map. theta is NaN
            # where V1 has no fibre direction, so downsample by normalized interpolation
            # (values-with-NaN-zeroed over a validity indicator) and mark voxels with <50%
            # fibre support as NaN — qsm-forward gives those no hollow-cylinder enrichment.
            angle_map=_w1("theta.nii.gz", th1) if th1 is not None else None,
        )
        rp = q.ReconParams(subject="1", B0=args.b0, TEs=tes, voxel_size=voxel, peak_snr=args.peak_snr,
                           random_seed=None if args.noiseless else SEED, se_TR=SE_TR, se_TEs=se_tes)
        extra = {}
        if args.hc_b0 is not None:
            extra["chisep_hc_b0"] = args.hc_b0
        q.generate_bids(
            tp2, rp, str(args.bids),
            save_field=True, save_chi_pos=True, save_chi_neg=True, save_r2prime=True,
            dr_pos_map=dr_pos_sim, dr_neg_map=dr_neg_sim, dr=DR_FIXED_POS,
            chisep_signal=True, chisep_multicompartment=args.multicompartment,
            save_se=not args.no_se, save_r2=args.r2_input,
            **extra,
        )
        pack = Path(__file__).with_name("pack_dataset.py")
        print(f"Packing {args.bids} -> {args.out} ...")
        subprocess.run([sys.executable, str(pack), str(args.bids), str(args.out), "--chisep"], check=True)
        if args.r2_input:
            r2s = sorted(Path(args.bids).glob("derivatives/**/*_R2map.nii*"))
            if not r2s:
                sys.exit("--r2-input: no *_R2map.nii* found in the BIDS derivatives")
            r2n = nib.load(str(r2s[0]))
            nib.save(r2n, str(args.out / "inputs" / "r2.nii.gz"))
            print("  wrote inputs/r2.nii.gz (ground-truth R2; Ridani R2' convention = R2*_fit - R2_GT)")
        if aniso and th1 is not None:  # ship θ (fibre-to-B0 angle) for the χ- orientation analysis (MEV)
            ref = nib.load(str(args.out / "groundtruth" / "chi-dia.nii.gz"))
            # clip to [0,90]: resize-path interpolation can overshoot slightly past 90° (cos²θ is
            # symmetric so it's harmless, but keep the angle physical)
            theta_out = np.clip(np.nan_to_num(th1), 0.0, 90.0).astype(np.float32)
            nib.save(nib.Nifti1Image(theta_out, ref.affine, ref.header),
                     str(args.out / "groundtruth" / "theta.nii.gz"))
            print("  wrote groundtruth/theta.nii.gz (fibre-to-B0 angle; for the θ-binned MSPE + MEV)")
        if args.wm_rois_src:  # ship the fibre-bundle WM sub-ROI atlas for the χ- per-ROI MSPE
            src = nib.load(str(args.wm_rois_src))
            ref = nib.load(str(args.out / "groundtruth" / "chi-dia.nii.gz"))
            lab = src.get_fdata()
            if src.shape != ref.shape:  # nearest-neighbour resample to the packed grid
                lab = q.resize(nib.Nifti1Image(np.rint(lab).astype(np.float32), src.affine, src.header),
                               np.asarray(ref.header.get_zooms()[:3], float), "nearest").get_fdata()
            nib.save(nib.Nifti1Image(np.rint(lab).astype(np.int16), ref.affine, ref.header),
                     str(args.out / "groundtruth" / "wm_rois.nii.gz"))
            print(f"  wrote groundtruth/wm_rois.nii.gz (fibre-bundle atlas, {int((np.rint(lab)>0).sum())} WM vox)")
        if not args.full_head:
            mask_derived_to_brain(args.out)
            print("Masked derived maps + ground truth to the brain (raw phase/magnitude kept whole-head).")
        print("Done. Re-score methods after regenerating.")

    if args.validate:
        v = Path(__file__).with_name("validate_phantom.py")
        subprocess.run([sys.executable, str(v), str(args.out)], check=True)


if __name__ == "__main__":
    main()
