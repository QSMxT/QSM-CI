#!/usr/bin/env python3
"""Derive a χ-separation dataset's method inputs from its noisy signal, with one fixed QSMxT pipeline.

QSM-CI's isolated χ-separation inputs are the phantom's ground truth (localfield, chimap) and an R2′
fitted from the noiseless signal. Under them a voxel-wise closed form (the null baseline) matches or
beats every method, because nothing upstream is in error. The derived inputs are what a real
acquisition gives every method instead: each one computed from the dataset's own noisy multi-echo GRE
(and spin echo, where the dataset has one) by the same QSMxT pipeline, whichever method reads them.

    <dataset>/derived/inputs/
      phase, magnitude, se_magnitude, dseg, params.json   the dataset's own (copied)
      mask.nii.gz            QSMxT's reconstruction mask: the dataset's brain mask less the rim
                             V-SHARP leaves out (derived χ is defined there, so it is scored there)
      localfield.nii.gz      run A: QSMxT defaults — ROMEO + phase-offset removal, weighted-average
                             B0, V-SHARP (12→2 mm), iLSQR, mean reference
      chimap.nii.gz          run A
      r2prime.nii.gz         qsmxt r2prime: max(R2* − R2, 0); R2* from run A (ARLO over every GRE
                             echo); R2 a mono-exponential (ARLO) fit of the spin echoes, or, for a
                             GRE-only dataset, the dataset's inputs/r2.nii.gz (an externally measured R2)
      chimap-echoes.nii.gz   run B, DECOMPOSE-QSM's reference pipeline (Chen et al. 2021 §3.6, as
                             QSM.rs's pipeline rules record it): Laplacian unwrapping, V-SHARP and
                             STAR-QSM on each echo (qsmxt --qsm-per-echo) — χ(TE), x,y,z,echo
      chimap-perecho.nii.gz  run B's QSM (the mean of the echoes' maps), the χ_total a method that
                             takes χ(TE) is given with it (as QSMxT runs DECOMPOSE)
    <dataset>/derived/groundtruth -> ../groundtruth

The mask is the dataset's own (never re-estimated), so every difference from the isolated inputs is
processing and noise. The spin echoes are independent Hahn echoes (not a CPMG train), so QSMxT's
EPG/MESE R2 model does not apply and R2 is the mono-exponential fit. `scripts/pipeline.py --inputs
derived` scores a method on these inputs.

Usage:
  python scripts/derive_chisep_inputs.py <dataset dir> [--qsmxt "apptainer exec qsmxt.sif qsmxt"]
"""
from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import tempfile
from pathlib import Path

import nibabel as nib
import numpy as np

GAMMA_MHZ = 42.576
RUN_A = ["--do-r2starmap"]
RUN_B = ["--unwrapping-algorithm", "laplacian", "--qsm-algorithm", "star", "--qsm-per-echo", "true"]
COPIED = ("phase", "magnitude", "se_magnitude", "dseg")


def _sidecar(nii: Path, meta: dict) -> None:
    nii.with_suffix(".json").write_text(json.dumps(meta, indent=1))


def stage_bids(dataset: Path, bids: Path) -> dict:
    """Write the dataset's raw acquisition as a one-subject BIDS tree QSMxT reads: one NIfTI + JSON
    per echo (MEGRE phase/magnitude; MESE magnitude when inputs/se_magnitude exists) and the brain
    mask as a `qsm-forward` derivative (`--use-custom-masks qsm-forward`). Returns what was staged."""
    inp = dataset / "inputs"
    prm = json.loads((inp / "params.json").read_text())
    anat = bids / "sub-1" / "anat"
    anat.mkdir(parents=True)
    (bids / "dataset_description.json").write_text(json.dumps({"Name": dataset.name, "BIDSVersion": "1.9.0"}))
    common = {"MagneticFieldStrength": prm["B0"], "ImagingFrequency": GAMMA_MHZ * prm["B0"]}
    staged = {"echoes": 0, "se_echoes": 0}
    for part, f in (("phase", "phase"), ("mag", "magnitude")):
        im = nib.load(str(inp / f"{f}.nii.gz"))
        data = np.asarray(im.dataobj, np.float32)
        if data.ndim == 3:
            data = data[..., None]
        if data.shape[-1] != len(prm["TE"]):
            raise SystemExit(f"{f}: {data.shape[-1]} echoes but params.json has {len(prm['TE'])} TEs")
        for e, te in enumerate(prm["TE"], 1):
            p = anat / f"sub-1_echo-{e}_part-{part}_MEGRE.nii"
            nib.save(nib.Nifti1Image(data[..., e - 1], im.affine), str(p))
            _sidecar(p, {**common, "EchoTime": te, "EchoNumber": e})
        staged["echoes"] = len(prm["TE"])
    se = inp / "se_magnitude.nii.gz"
    if se.exists():
        im = nib.load(str(se))
        data = np.asarray(im.dataobj, np.float32)
        data = data[..., None] if data.ndim == 3 else data
        se_te = prm.get("se_TE")
        if not se_te or len(se_te) != data.shape[-1]:
            raise SystemExit("inputs/se_magnitude.nii.gz needs params.json se_TE, one per spin echo")
        for e, te in enumerate(se_te, 1):
            p = anat / f"sub-1_echo-{e}_part-mag_MESE.nii"
            nib.save(nib.Nifti1Image(data[..., e - 1], im.affine), str(p))
            _sidecar(p, {**common, "EchoTime": te, "EchoNumber": e,
                         "RepetitionTime": prm.get("se_TR", 1.5)})
        staged["se_echoes"] = len(se_te)
    der = bids / "derivatives" / "qsm-forward"
    (der / "sub-1" / "anat").mkdir(parents=True)
    (der / "dataset_description.json").write_text(json.dumps(
        {"Name": "qsm-forward", "BIDSVersion": "1.9.0", "DatasetType": "derivative",
         "GeneratedBy": [{"Name": "qsm-forward"}]}))
    m = nib.load(str(inp / "mask.nii.gz"))
    nib.save(nib.Nifti1Image((np.asarray(m.dataobj) > 0).astype(np.uint8), m.affine),
             str(der / "sub-1" / "anat" / "sub-1_mask.nii"))
    return staged


def commands(qsmxt: list, bids: Path, work: Path, staged: dict, prm: dict, r2_input: "Path | None") -> list:
    """The QSMxT command lines, in order (run A, run B, R2 fit, R2′)."""
    mask = bids / "derivatives" / "qsm-forward" / "sub-1" / "anat" / "sub-1_mask.nii"
    cmds = [qsmxt + ["run", str(bids), str(work / "A"), "--use-custom-masks", "qsm-forward"] + RUN_A,
            qsmxt + ["run", str(bids), str(work / "B"), "--use-custom-masks", "qsm-forward"] + RUN_B]
    if staged["se_echoes"]:
        se = [str(bids / "sub-1" / "anat" / f"sub-1_echo-{e}_part-mag_MESE.nii")
              for e in range(1, staged["se_echoes"] + 1)]
        cmds.append(qsmxt + ["r2star"] + se + ["-m", str(mask), "-o", str(work / "R2.nii"),
                             "--echo-times"] + [repr(float(t)) for t in prm["se_TE"]])
    elif r2_input is None:
        raise SystemExit("no spin echo and no inputs/r2.nii.gz: R2′ = R2* − R2 cannot be measured")
    cmds.append(qsmxt + ["r2prime", "--r2star", str(work / "A/derivatives/qsmxt/sub-1/anat/sub-1_R2starmap.nii"),
                         "--r2", str(work / "R2.nii"), "-m", str(mask), "-o", str(work / "R2prime.nii")])
    return cmds


def pack(dataset: Path, work: Path) -> Path:
    """Write <dataset>/derived/ from the QSMxT outputs in `work`."""
    inp, out = dataset / "inputs", dataset / "derived"
    if out.exists():
        shutil.rmtree(out)
    (out / "inputs").mkdir(parents=True)
    os.symlink("../groundtruth", out / "groundtruth")
    ref = nib.load(str(inp / "mask.nii.gz"))
    L = lambda p: np.asarray(nib.load(str(p)).dataobj, np.float32)
    A, Bq = work / "A/derivatives/qsmxt", work / "B/derivatives/qsmxt"
    qmask = L(A / "sub-1/anat/sub-1_desc-qsm_mask.nii") > 0
    save = lambda a, name, dt=np.float32: nib.save(nib.Nifti1Image(a.astype(dt), ref.affine),
                                                   str(out / "inputs" / name))
    save(qmask, "mask.nii.gz", np.uint8)
    save(L(A / "workflow/sub-1/bgremove/sub-1_localfield.nii") * qmask, "localfield.nii.gz")
    save(L(A / "sub-1/anat/sub-1_Chimap.nii") * qmask, "chimap.nii.gz")
    save(L(work / "R2prime.nii") * qmask, "r2prime.nii.gz")
    echoes = sorted((Bq / "sub-1/anat").glob("sub-1_desc-echo*_Chimap.nii"),
                    key=lambda p: int(p.name.split("desc-echo")[1].split("_")[0]))
    if not echoes:
        raise SystemExit("run B wrote no per-echo QSM (desc-echo<n>_Chimap)")
    save(np.stack([L(e) * qmask for e in echoes], axis=-1), "chimap-echoes.nii.gz")
    save(L(Bq / "sub-1/anat/sub-1_Chimap.nii") * qmask, "chimap-perecho.nii.gz")
    for f in COPIED:
        if (inp / f"{f}.nii.gz").exists():
            shutil.copy(inp / f"{f}.nii.gz", out / "inputs" / f"{f}.nii.gz")
    shutil.copy(inp / "params.json", out / "inputs" / "params.json")
    for run in ("A", "B"):
        meth = work / run / "derivatives/qsmxt/methods.md"
        if meth.exists():
            shutil.copy(meth, out / f"methods-{run}.md")
    return out


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dataset", type=Path, help="χ-separation dataset dir (inputs/ + groundtruth/)")
    ap.add_argument("--qsmxt", default="qsmxt",
                    help="the qsmxt command, e.g. 'apptainer exec <image>.sif qsmxt' (default: qsmxt on PATH)")
    ap.add_argument("--work", type=Path, default=None, help="keep QSMxT's working tree here")
    a = ap.parse_args(argv)
    qsmxt = shlex.split(a.qsmxt)
    work = a.work or Path(tempfile.mkdtemp(prefix="derive-"))
    work.mkdir(parents=True, exist_ok=True)
    prm = json.loads((a.dataset / "inputs" / "params.json").read_text())
    staged = stage_bids(a.dataset, work / "bids")
    r2_input = a.dataset / "inputs" / "r2.nii.gz"
    r2_input = r2_input if r2_input.exists() else None
    if not staged["se_echoes"] and r2_input is not None:
        shutil.copy(r2_input, work / "R2.nii.gz")
        nib.save(nib.load(str(work / "R2.nii.gz")), str(work / "R2.nii"))
    subprocess.run(qsmxt + ["--version"], check=True)
    for cmd in commands(qsmxt, work / "bids", work, staged, prm, r2_input):
        print("+", shlex.join(cmd), flush=True)
        subprocess.run(cmd, check=True)
    out = pack(a.dataset, work)
    print(f"derived inputs -> {out}")
    if a.work is None:
        shutil.rmtree(work)


if __name__ == "__main__":
    main()
