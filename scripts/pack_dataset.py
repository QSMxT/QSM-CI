#!/usr/bin/env python3
"""Pack a qsm-forward BIDS output into the QSM-CI artifact layout.

qsm-forward produces raw multi-echo NIfTI + derivatives (fieldmap, fieldmap-local, Chimap, dseg,
mask). This flattens that into the canonical artifacts QSM-CI submissions consume/produce (see
stages.yml / CONTRACT.md):

    <out>/inputs/       phase.nii.gz  magnitude.nii.gz  mask.nii.gz  params.json
    <out>/groundtruth/  totalfield.nii.gz  localfield.nii.gz  chimap.nii.gz  dseg.nii.gz

A χ-separation phantom (qsm-forward wrote `*_Chimap-pos`, or `--chisep`) packs differently: the local
field, χ_total and R2′ become inputs/, the χ+/χ− source maps are the scored groundtruth/, and the
qsm-forward chi-sep extras are carried along when present:

    inputs/r2prime.nii.gz              `*_R2prime` — what methods get (fitted from the simulated
                                       signal when the phantom was made with r2prime_source=fitted)
    inputs/r2.nii.gz                   `*_R2map`, the ground-truth R2
    groundtruth/r2prime-formula.nii.gz `*_desc-formula_R2prime`, the R2′ the phantom imposes
                                       (R2′ = Dr+|χ+| + Dr−|χ−|). Reference only: never mounted.
    groundtruth/chisep.json            `*_chisep.json`, the phantom configuration and relaxivity
    groundtruth/theta.nii.gz           `*_fibreangle`, fibre-to-B0 angle (degrees)
    groundtruth/wm_rois.nii.gz         `*_desc-wmrois_dseg`, the white-matter sub-ROI atlas

When qsm-forward also wrote controlled-degradation inputs (`qsm_forward.degrade`, a preset's
`degrade_levels`), each level ships beside the ground-truth inputs, under its own directory and the
canonical artifact names, without changing inputs/:

    inputs-l3/        localfield  chimap  chimap-echoes  r2prime  mask (.nii.gz) — the level's
                      `*_desc-degradedL3_{fieldmap-local,Chimap,Chimap-echoes,R2prime,mask}`
    groundtruth/degradation-l3.json   `*_desc-degradedL3_degradation.json`: every parameter, the
                      seed, the qsm-forward version and the calibration spread. Reference only.

The scorer mounts inputs-<level>/ in place of inputs/ for those five artifacts (pipeline.py
--inputs <level>); the raw signal, params and the ground truth are shared by every level.

and params.json gains `chisep_dr_hz_per_ppm`, the paramagnetic relaxivity Dr+ the phantom imposes
(documentation only; no method reads it, they keep their published defaults).

`inputs/` is the public boundary for the field-mapping / end-to-end stage. `groundtruth/` holds the
per-stage scoring targets *and* the boundaries mounted (at run time only) as isolated-mode inputs to
downstream stages. For the scoring phantom, `groundtruth/` comes from the OSF zip (not committed); for a dev phantom it
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


def stack_echoes(anat: Path, part: str, suffix: str = "MEGRE", required: bool = True):
    files = sorted(glob.glob(str(anat / f"*part-{part}_{suffix}.nii*")), key=echo_key)
    if not files:
        # single-echo files carry no part-<x> tag
        files = sorted(glob.glob(str(anat / f"*_{suffix}.nii*")), key=echo_key)
    if not files:
        if required:
            raise SystemExit(f"no {part} {suffix} echoes in {anat}")
        return None, None
    imgs = [nib.load(f) for f in files]
    data = np.stack([im.get_fdata(dtype=np.float64) for im in imgs], axis=-1)
    return data, imgs[0].affine


def params_from_sidecars(anat: Path) -> dict:
    files = sorted(glob.glob(str(anat / "*part-phase_MEGRE.json")), key=echo_key)
    sides = [json.load(open(f)) for f in files]
    s0 = sides[0]
    vox = s0.get("VoxelSize") or [1.0, 1.0, 1.0]
    params = {
        "TE": [s["EchoTime"] for s in sides],
        "B0": s0["MagneticFieldStrength"],
        "B0_dir": list(s0.get("B0_dir", [0, 0, 1])),
        "voxel_size": [float(v) for v in vox],
    }
    # Optional matched spin-echo acquisition (magnitude decays with R2, not R2*).
    se = sorted(glob.glob(str(anat / "*_MESE.json")), key=echo_key)
    if se:
        se_sides = [json.load(open(f)) for f in se]
        params["se_TE"] = [s["EchoTime"] for s in se_sides]
        params["se_TR"] = se_sides[0].get("RepetitionTime")
    return params


def chisep_relaxivity(meta: dict) -> "float | None":
    """The paramagnetic relaxivity Dr+ (Hz/ppm) a qsm-forward `*_chisep.json` records: `Dr` for a
    co-located (linear) phantom, where χ+ and χ− share it, or `DrPos` for the region-disjoint Ridani
    model, whose Dr− is orientation-dependent (its maximum is `DrNegMax` in the same block)."""
    relax = meta.get("Relaxivity") or {}
    dr = relax.get("Dr", relax.get("DrPos"))
    return float(dr) if dr is not None else None


# qsm-forward degradation outputs (`*_desc-degraded<L>_<name>`) -> canonical artifact names.
DEGRADED_ARTIFACTS = {"fieldmap-local": "localfield", "Chimap": "chimap", "Chimap-echoes": "chimap-echoes",
                      "R2prime": "r2prime", "mask": "mask"}


def ground_truth_stem(deriv: Path) -> str:
    """The derivatives' file stem (e.g. `sub-1_run-1`): the prefix of the ground-truth `*_Chimap`.
    Entity-tagged maps that share the suffix (`*_desc-degradedL3_Chimap`, …) are not the ground truth."""
    hits = sorted(p for p in glob.glob(str(deriv / "*_Chimap.nii*")) if "_desc-" not in os.path.basename(p))
    if not hits:
        raise SystemExit(f"no ground-truth *_Chimap in {deriv}")
    return os.path.basename(hits[0]).split("_Chimap")[0]


def degraded_levels(deriv: Path, pre: str) -> list:
    """The degradation levels qsm-forward wrote for this phantom (`L3`, …), sorted."""
    tags = {re.search(r"_desc-degraded(L\d+)_", os.path.basename(p)).group(1)
            for p in glob.glob(str(deriv / f"{pre}_desc-degradedL*_*.nii*"))}
    return sorted(tags)


def pack_degraded(deriv: Path, pre: str, out: Path) -> None:
    """Ship each degradation level's inputs as inputs-<level>/ and its sidecar as
    groundtruth/degradation-<level>.json (see the module docstring)."""
    for level in degraded_levels(deriv, pre):
        low = level.lower()
        for src, dst in DEGRADED_ARTIFACTS.items():
            hit = glob.glob(str(deriv / f"{pre}_desc-degraded{level}_{src}.nii*"))
            if hit:
                im = nib.load(hit[0])
                save(out / f"inputs-{low}" / f"{dst}.nii.gz", im.get_fdata(), im.affine)
        side = deriv / f"{pre}_desc-degraded{level}_degradation.json"
        if side.exists():
            (out / "groundtruth").mkdir(parents=True, exist_ok=True)
            (out / "groundtruth" / f"degradation-{low}.json").write_text(side.read_text())
        print(f"  (packed degraded inputs {level} -> inputs-{low}/)")


def save(path: Path, data: np.ndarray, affine: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    nib.save(nib.Nifti1Image(data.astype(np.float32), affine), str(path))


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    force_chisep = "--chisep" in sys.argv[1:]
    if len(args) != 2:
        raise SystemExit(__doc__)
    bids, out = Path(args[0]), Path(args[1])
    anat = find_sub_anat(bids)
    deriv = sorted(glob.glob(str(bids / "derivatives" / "qsm-forward" / "sub-*" / "anat")))
    if not deriv:
        raise SystemExit("no derivatives/qsm-forward/sub-*/anat (run qsm-forward with save_field=True)")
    deriv = Path(deriv[0])
    pre = ground_truth_stem(deriv)

    # inputs/
    phase, aff = stack_echoes(anat, "phase")
    mag, _ = stack_echoes(anat, "mag")
    save(out / "inputs" / "phase.nii.gz", phase, aff)
    save(out / "inputs" / "magnitude.nii.gz", mag, aff)
    # optional matched multi-echo spin-echo magnitude (for methods that estimate R2' = R2* - R2)
    se_mag, se_aff = stack_echoes(anat, "mag", suffix="MESE", required=False)
    if se_mag is not None:
        save(out / "inputs" / "se_magnitude.nii.gz", se_mag, se_aff)
        print(f"  (packed {se_mag.shape[-1]}-echo spin-echo magnitude)")
    mask = nib.load(str(deriv / f"{pre}_mask.nii"))
    save(out / "inputs" / "mask.nii.gz", mask.get_fdata(), mask.affine)
    params = params_from_sidecars(anat)

    # χ-separation phantom? (has the paramagnetic/diamagnetic source maps). If so, the local field,
    # χ_total and R2' are PROVIDED inputs (methods invert them), and the scored targets are χ+/χ−.
    chisep = force_chisep or bool(glob.glob(str(deriv / f"{pre}_Chimap-pos.nii*")))
    meta_json = sorted(glob.glob(str(deriv / f"{pre}_chisep.json"))) if chisep else []
    if meta_json:
        # The phantom's configuration ships beside its ground truth; its Dr+ is recorded in
        # params.json for documentation. No method reads it: they keep their published defaults.
        meta = json.loads(Path(meta_json[0]).read_text())
        (out / "groundtruth").mkdir(parents=True, exist_ok=True)
        (out / "groundtruth" / "chisep.json").write_text(json.dumps(meta, indent=2) + "\n")
        dr = chisep_relaxivity(meta)
        if dr is not None:
            params["chisep_dr_hz_per_ppm"] = dr
    (out / "inputs").mkdir(parents=True, exist_ok=True)
    (out / "inputs" / "params.json").write_text(json.dumps(params, indent=2) + "\n")

    # groundtruth/  (qsm-forward name -> canonical artifact name)
    if chisep:
        # χ-sep inputs: local field + χ_total + R2' are given to the method. Chimap-echoes, when
        # qsm-forward writes it, is the echo-dependent χ(TE), one map per echo (x,y,z,echo; ppm):
        # the optional `chimap-echoes` input DECOMPOSE-QSM takes as its per-echo QSM (stages.yml).
        inp = {"fieldmap-local": "localfield", "Chimap": "chimap", "Chimap-echoes": "chimap-echoes",
               "R2prime": "r2prime"}
        for src, dst in inp.items():
            hit = glob.glob(str(deriv / f"{pre}_{src}.nii*"))
            if hit:
                im = nib.load(hit[0])
                save(out / "inputs" / f"{dst}.nii.gz", im.get_fdata(), im.affine)
        # The R2' the phantom imposes (formula) is a reference beside the ground truth, not an input:
        # inputs/r2prime above is `*_R2prime`, which is fitted from the simulated signal when the
        # phantom was made with r2prime_source=fitted.
        gt = {"Chimap-pos": "chi-para", "Chimap-neg": "chi-dia", "Chimap": "chimap", "dseg": "dseg",
              "desc-formula_R2prime": "r2prime-formula"}
        # qsm-forward chi-sep extras, copied with their own dtype and header: the ground-truth R2
        # (an input under the Ridani R2' = R2*_fit - R2 convention), the fibre-to-B0 angle and the
        # white-matter sub-ROI atlas (both scoring aids).
        extras = {"R2map": "inputs/r2", "fibreangle": "groundtruth/theta",
                  "desc-wmrois_dseg": "groundtruth/wm_rois"}
        for src, dst in extras.items():
            hit = glob.glob(str(deriv / f"{pre}_{src}.nii*"))
            if hit:
                (out / dst).parent.mkdir(parents=True, exist_ok=True)
                nib.save(nib.load(hit[0]), str(out / f"{dst}.nii.gz"))
        pack_degraded(deriv, pre, out)
    else:
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
