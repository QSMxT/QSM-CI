#!/usr/bin/env python3
"""gen_chisep — build a QSM-CI χ-separation phantom with qsm-forward.

The phantoms themselves (the Ridani et al. 2026 χ+/χ- construction, the signal models and the
named configurations) live in qsm-forward (`qsm_forward.chisep`). This script runs one of its
presets, packs the BIDS output into QSM-CI's inputs/ + groundtruth/ layout (pack_dataset.py),
masks the derived maps to the brain, and optionally validates the result.

THE SHIPPED PHANTOMS are the qsm-forward presets of the same name:
  chisep-mc                      7 T, 8 echoes, hollow-cylinder white matter, SE, SNR 100
  ridani-3t-iso / -3t-aniso / -7t-aniso   as published by Ridani et al. (noiseless, native grid)
  decompose-3t / -3t-noise       ridani-3t-aniso sources at 1 mm with DECOMPOSE's three-pool
                                 signal (matched to DECOMPOSE, as chisep-mc is to HC-ChiSep)

  python scripts/gen_chisep.py --preset chisep-mc \\
      --wm-rois-src <Masks/WM_fibers_seg.nii.gz from OSF 9xwhz> --out data/sim/chisep-mc

  --wm-rois-src is needed to match what is shipped: every OSF phantom carries
  groundtruth/wm_rois.nii.gz, and without it the per-ROI MSPE metric is silently dropped
  (pipeline.py passes wm_rois only if it exists). The atlas is Ridani et al.'s public file (OSF
  project 9xwhz, Masks/WM_fibers_seg.nii.gz, md5 06b1aec8b2a8a001e7e856c6c1fddcf0);
  scripts/mirror_ridani_osf.py mirrors that project.

Any preset field can be overridden (see qsm_forward.chisep.ChisepConfig), e.g.
  python scripts/gen_chisep.py --preset chisep-mc --set peak_snr=50 --out data/sim/chisep-snr50

Usage (python with qsm-forward installed):
  python scripts/gen_chisep.py --preset ridani-3t-aniso --maps-only --validate   # χ+/χ-/R2' only
  python scripts/gen_chisep.py --preset decompose-3t --out data/sim/decompose-3t  # full sim
"""

from __future__ import annotations

import argparse
import ast
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import nibabel as nib


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


def write_maps_dataset(out: Path, maps, full_head: bool):
    """--maps-only: the native-grid χ+/χ-/R2' ground truth in the QSM-CI layout, no simulation."""
    tp = maps.tissue
    mask = tp.mask.get_fdata() > 0
    b = 1.0 if full_head else mask.astype(np.float32)

    def save(rel, data):
        p = out / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        nib.save(nib.Nifti1Image(np.asarray(data, np.float32), tp.nii_affine, tp.nii_header), str(p))
    save("inputs/chimap.nii.gz", maps.chi_total * b)
    save("inputs/r2prime.nii.gz", maps.r2prime * b)
    save("inputs/mask.nii.gz", mask.astype(np.float32))
    save("groundtruth/chi-para.nii.gz", maps.chi_pos * b)
    save("groundtruth/chi-dia.nii.gz", np.abs(maps.chi_neg) * b)


def parse_override(text: str):
    key, sep, val = text.partition("=")
    if not sep:
        raise argparse.ArgumentTypeError(f"--set expects FIELD=VALUE, got {text!r}")
    try:
        return key.strip(), ast.literal_eval(val.strip())
    except (ValueError, SyntaxError):
        return key.strip(), val.strip()


def main() -> None:
    try:
        from qsm_forward import chisep
    except ModuleNotFoundError:
        sys.exit("import qsm_forward failed — install qsm-forward (with qsm_forward.chisep).")

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--preset", required=True, choices=sorted(chisep.PRESETS),
                    help="qsm-forward chi-sep preset (qsm_forward.chisep.PRESETS)")
    ap.add_argument("--set", type=parse_override, action="append", default=[], metavar="FIELD=VALUE",
                    help="override one ChisepConfig field of the preset (repeatable)")
    ap.add_argument("--qsmf-data", type=Path, default=Path.home() / "repos/qsm/qsm-forward/data",
                    help="QSM Challenge 2.0 head-model data dir (chimodel/, maps/, masks/, raw/)")
    ap.add_argument("--out", type=Path, default=Path("data/sim/chisep"))
    ap.add_argument("--bids", type=Path, default=None,
                    help="where qsm-forward writes its BIDS output (default: a temporary directory)")
    ap.add_argument("--wm-rois-src", type=Path, default=None,
                    help="fibre-bundle WM sub-ROI atlas (Ridani OSF 9xwhz Masks/WM_fibers_seg.nii.gz) to "
                         "ship as groundtruth/wm_rois.nii.gz — the label map the χ- per-ROI MSPE averages over")
    ap.add_argument("--full-head", action="store_true",
                    help="keep the derived maps (chimap, R2', local field) and ground truth over the whole "
                         "head; by default they are masked to the brain while the raw phase/magnitude keep "
                         "the whole-head background field")
    ap.add_argument("--maps-only", action="store_true", help="only build χ+/χ-/R2', no simulation")
    ap.add_argument("--validate", action="store_true", help="run validate_phantom.py on the written dataset")
    args = ap.parse_args()

    config = chisep.preset(args.preset, **dict(args.set))
    print(f"Preset {args.preset}: {config}")
    data = str(args.qsmf_data)

    if args.maps_only:
        write_maps_dataset(args.out, chisep.build_chisep_maps(data, config), args.full_head)
        print(f"--maps-only: wrote maps dataset to {args.out} (no field/signal sim).")
    else:
        with tempfile.TemporaryDirectory() as tmp:
            bids = args.bids or Path(tmp) / "bids"
            chisep.generate_chisep_bids(data, str(bids), config,
                                        wm_rois=str(args.wm_rois_src) if args.wm_rois_src else None)
            pack = Path(__file__).with_name("pack_dataset.py")
            print(f"Packing {bids} -> {args.out} ...")
            subprocess.run([sys.executable, str(pack), str(bids), str(args.out), "--chisep"], check=True)
        if not args.full_head:
            mask_derived_to_brain(args.out)
            print("Masked derived maps + ground truth to the brain (raw phase/magnitude kept whole-head).")
        print("Done. Re-score methods after regenerating.")

    if args.validate:
        v = Path(__file__).with_name("validate_phantom.py")
        subprocess.run([sys.executable, str(v), str(args.out)], check=True)


if __name__ == "__main__":
    main()
