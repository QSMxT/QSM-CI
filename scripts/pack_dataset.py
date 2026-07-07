#!/usr/bin/env python3
"""Pack a qsm-forward BIDS output into the QSM-CI artifact layout.

qsm-forward produces raw multi-echo NIfTI + derivatives (fieldmap, fieldmap-local, Chimap, dseg,
mask). This flattens that into the canonical artifacts QSM-CI submissions consume/produce (see
stages.yml / CONTRACT.md):

    <out>/inputs/       phase.nii.gz  magnitude.nii.gz  mask.nii.gz  params.json
    <out>/groundtruth/  totalfield.nii.gz  localfield.nii.gz  chimap.nii.gz  dseg.nii.gz

`inputs/` is the public boundary for the field-mapping / end-to-end stage. `groundtruth/` holds the
per-stage scoring targets *and* the boundaries mounted (at run time only) as isolated-mode inputs to
downstream stages. For the scoring phantom, `groundtruth/` is held out (OSF); for a dev phantom it
may be released openly.

Usage:
    python pack_dataset.py <bids_dir> <out_dir>

Generate the BIDS input first with qsm-forward, e.g. (from the qsm-forward checkout):
    python -c "import numpy as np, qsm_forward as q; \
      chi=q.generate_susceptibility_phantom([96,96,60],0,0.005,[6,6,5,4],[0.05,0.1,-0.1,0.2]); \
      q.generate_bids(q.TissueParams(chi=chi), q.ReconParams(B0=3.0,peak_snr=100,random_seed=42), \
      'BIDS', save_field=True)"
"""

from __future__ import annotations

import glob
import json
import os
import re
import sys
from pathlib import Path

import nibabel as nib
import numpy as np


def find_sub_anat(bids: Path) -> Path:
    hits = sorted(glob.glob(str(bids / "sub-*" / "anat")))
    if not hits:
        raise SystemExit(f"no sub-*/anat under {bids}")
    return Path(hits[0])


def echo_key(path: str) -> int:
    m = re.search(r"echo-(\d+)", path)
    return int(m.group(1)) if m else 0


def stack_echoes(anat: Path, part: str) -> tuple[np.ndarray, np.ndarray]:
    files = sorted(glob.glob(str(anat / f"*part-{part}_MEGRE.nii*")), key=echo_key)
    if not files:
        raise SystemExit(f"no {part} echoes in {anat}")
    imgs = [nib.load(f) for f in files]
    data = np.stack([im.get_fdata(dtype=np.float64) for im in imgs], axis=-1)
    return data, imgs[0].affine


def params_from_sidecars(anat: Path) -> dict:
    files = sorted(glob.glob(str(anat / "*part-phase_MEGRE.json")), key=echo_key)
    sides = [json.load(open(f)) for f in files]
    s0 = sides[0]
    vox = s0.get("VoxelSize") or [1.0, 1.0, 1.0]
    return {
        "contract": "v2",
        "TE": [s["EchoTime"] for s in sides],
        "B0": s0["MagneticFieldStrength"],
        "B0_dir": list(s0.get("B0_dir", [0, 0, 1])),
        "voxel_size": [float(v) for v in vox],
    }


def save(path: Path, data: np.ndarray, affine: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    nib.save(nib.Nifti1Image(data.astype(np.float32), affine), str(path))


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    bids, out = Path(sys.argv[1]), Path(sys.argv[2])
    anat = find_sub_anat(bids)
    deriv = sorted(glob.glob(str(bids / "derivatives" / "qsm-forward" / "sub-*" / "anat")))
    if not deriv:
        raise SystemExit("no derivatives/qsm-forward/sub-*/anat (run qsm-forward with save_field=True)")
    deriv = Path(deriv[0])
    pre = os.path.basename(glob.glob(str(deriv / "*_Chimap.nii*"))[0]).split("_Chimap")[0]

    # inputs/
    phase, aff = stack_echoes(anat, "phase")
    mag, _ = stack_echoes(anat, "mag")
    save(out / "inputs" / "phase.nii.gz", phase, aff)
    save(out / "inputs" / "magnitude.nii.gz", mag, aff)
    mask = nib.load(str(deriv / f"{pre}_mask.nii"))
    save(out / "inputs" / "mask.nii.gz", mask.get_fdata(), mask.affine)
    (out / "inputs").mkdir(parents=True, exist_ok=True)
    (out / "inputs" / "params.json").write_text(json.dumps(params_from_sidecars(anat), indent=2) + "\n")

    # groundtruth/  (qsm-forward name -> canonical artifact name)
    gt = {"fieldmap": "totalfield", "fieldmap-local": "localfield", "Chimap": "chimap", "dseg": "dseg"}
    for src, dst in gt.items():
        hit = glob.glob(str(deriv / f"{pre}_{src}.nii*"))
        if not hit:
            print(f"  (skip {src}: not found)")
            continue
        im = nib.load(hit[0])
        save(out / "groundtruth" / f"{dst}.nii.gz", im.get_fdata(), im.affine)

    print(f"packed {bids} -> {out}")
    for p in sorted(glob.glob(str(out / "**" / "*"), recursive=True)):
        if os.path.isfile(p):
            print("  ", os.path.relpath(p, out), f"({os.path.getsize(p)//1024} KB)")


if __name__ == "__main__":
    main()
