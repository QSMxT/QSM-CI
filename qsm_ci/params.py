"""params.json assembly and multi-echo input placement.

Builds a stage's params.json from --te/--field-strength/--b0-dir/--voxel-size (or maps a BIDS MEGRE
sidecar onto the same schema), and places consumed NIfTIs into the input dir — stacking per-echo 3D
files into one 4D artifact when needed. Kept dependency-light (nibabel/numpy imported lazily, only
when actually stacking echoes) so the common single-file path has no heavy imports.
"""

from __future__ import annotations

import glob
import gzip
import json
import re
import shutil
import struct
from pathlib import Path

from .stages import STAGES

# Which consumed artifacts a method can run without is ONE rule, stages.is_optional — shared with the
# help text and the workflow-engine wrappers so they can't disagree.

# Multi-echo artifacts: a stage wants one 4D NIfTI (x,y,z,echo), but a caller with BIDS data has one
# 3D file per echo. These flags accept several files and we stack them into the 4D artifact.
STACKABLE_ARTIFACTS = {"phase", "magnitude"}


def _nifti_voxel_size(path) -> "list[float] | None":
    """Read pixdim[1:4] (mm) straight from a NIfTI-1 or NIfTI-2 header — no nibabel dependency."""
    if not path or not Path(path).exists():
        return None
    opener = gzip.open if str(path).endswith(".gz") else open
    try:
        with opener(path, "rb") as f:
            hdr = f.read(352)
        if len(hdr) < 352:
            return None
        for endian in ("<", ">"):  # header endianness is whichever makes sizeof_hdr match
            size = struct.unpack(endian + "i", hdr[0:4])[0]
            if size == 348:      # NIfTI-1: pixdim = 8 x float32 at byte 76
                pixdim = struct.unpack(endian + "8f", hdr[76:108])
            elif size == 540:    # NIfTI-2: pixdim = 8 x float64 at byte 104
                pixdim = struct.unpack(endian + "8d", hdr[104:168])
            else:
                continue
            vs = [abs(pixdim[1]), abs(pixdim[2]), abs(pixdim[3])]
            return vs if all(v > 0 for v in vs) else None
    except Exception:  # noqa: BLE001 — unreadable header; the caller decides what that means
        return None
    return None


def _primary_path(args, consumes: list):
    """The first consumed image input the caller supplied — whose header gives the voxel size.
    A multi-echo flag (--phase/--magnitude, nargs="+") holds a LIST of files; any echo's header
    describes the same grid, so take the first. Never a list, never params."""
    for art in consumes:
        if art == "params":
            continue
        v = getattr(args, art, None)
        if v:
            return v[0] if isinstance(v, (list, tuple)) else v
    return None


def _voxel_size(args, consumes: list, fallback=None) -> list:
    """Voxel size for params.json: --voxel-size if given, else the primary input's NIfTI header,
    else `fallback` (a BIDS sidecar's VoxelSize). Refuses to guess: a silent 1 mm default would
    change the dipole kernel without a word, so an unreadable header is an error."""
    if args.voxel_size is not None:
        return list(args.voxel_size)
    primary = _primary_path(args, consumes)
    voxel = _nifti_voxel_size(primary) or fallback
    if not voxel:
        raise SystemExit(f"could not read the voxel size from the NIfTI header of {primary} — "
                         "pass --voxel-size X Y Z (mm).")
    return list(voxel)


def _place_input(src, dest: Path) -> None:
    """Put a consumed NIfTI at <name>.nii.gz, gzip-compressing a plain .nii on the way in."""
    src = str(src)
    if src.endswith(".nii") and str(dest).endswith(".nii.gz"):
        with open(src, "rb") as fi, gzip.open(dest, "wb") as fo:
            shutil.copyfileobj(fi, fo)
    else:
        shutil.copy(src, dest)


def _echo_key(path) -> int:
    m = re.search(r"echo-?(\d+)", str(path))
    return int(m.group(1)) if m else 0


def _place_echoes(paths: list, dest: Path, log) -> None:
    """Place a multi-echo artifact: one file goes in as-is; several 3D echoes are stacked into 4D.

    When every filename carries a BIDS `echo-<n>`, echoes are ordered by that number (so echo-10
    sorts after echo-2); otherwise the given order is kept. The stacked file must line up with the
    `TE` list in params.json."""
    if len(paths) == 1:
        _place_input(paths[0], dest)
        return
    import nibabel as nib
    import numpy as np
    ordered = sorted(paths, key=_echo_key) if all(re.search(r"echo-?\d+", str(p)) for p in paths) else list(paths)
    imgs = [nib.load(str(p)) for p in ordered]
    data = np.stack([im.get_fdata(dtype=np.float64) for im in imgs], axis=-1)
    dest.parent.mkdir(parents=True, exist_ok=True)
    nib.save(nib.Nifti1Image(data.astype(np.float32), imgs[0].affine), str(dest))
    log(f"  stacked {len(ordered)} echoes → {dest.name}")


def _ensure_te(te: list, stage: str) -> list:
    """BFR/dipole don't use TE physically — the field is already in ppm and the TE·B0 scaling that
    some recon code applies cancels out — but that code still indexes TE(1). Supply a nominal
    placeholder so an omitted --te writes TE=[1.0] rather than an empty list that blows up the
    container (MATLAB: "Index exceeds array bounds"). Never fabricates TE for phase-consuming
    stages (field-mapping / end-to-end) — those genuinely need a real echo time."""
    if te or "phase" in STAGES[stage]["consumes"]:
        return te
    return [1.0]


def _params_dict(args, stage: str) -> dict:
    """Assemble a params.json dict from --te/--field-strength/--b0-dir/--voxel-size (+ defaults).

    B0_dir defaults to +z; voxel size is read from the primary input's NIfTI header when not given.
    Echo times and field strength are only required for stages that consume phase (field-mapping);
    BFR/dipole work in ppm and don't use them, so they get harmless placeholders.
    """
    consumes = STAGES[stage]["consumes"]
    needs_echo = "phase" in consumes
    te = list(args.te) if args.te else []
    b0 = args.field_strength
    if needs_echo and (not te or b0 is None):
        raise SystemExit(
            f"the {stage} stage needs echo times and field strength — pass "
            "--te SEC [SEC ...] and --field-strength TESLA, or give a --params file.")
    te = _ensure_te(te, stage)  # BFR/dipole: nominal placeholder if omitted (cancels; never empty)
    if b0 is None:
        b0 = 3.0  # unused by BFR/dipole; a contract placeholder
    b0_dir = list(args.b0_dir) if args.b0_dir is not None else [0.0, 0.0, 1.0]
    voxel = _voxel_size(args, consumes)
    return {"TE": [float(t) for t in te], "B0": float(b0),
            "B0_dir": [float(x) for x in b0_dir], "voxel_size": [float(v) for v in voxel]}


def _params_summary(params: dict, stage: str) -> str:
    """One-line echo of the params actually used by a stage. Field-mapping consumes TE + B0;
    BFR/dipole work in ppm and use only B0 direction + voxel size, so don't imply otherwise."""
    if "phase" in STAGES[stage]["consumes"]:
        return (f"TE={params['TE']} B0={params['B0']} "
                f"B0_dir={params['B0_dir']} voxel_size={params['voxel_size']}")
    return (f"B0_dir={params['B0_dir']} voxel_size={params['voxel_size']}  "
            f"(TE / field strength not used by this stage)")


def _looks_like_sidecar(obj: dict) -> bool:
    """A BIDS MEGRE sidecar carries these keys; a QSM-CI params.json does not."""
    return isinstance(obj, dict) and ("EchoTime" in obj or "MagneticFieldStrength" in obj)


def _sidecar_te(sidecar_path: Path) -> "list[float]":
    """Echo times (s) for the whole acquisition: all `*part-phase*MEGRE.json` in the sidecar's
    directory, in echo order. Falls back to just this file's EchoTime."""
    def echo_no(f: str) -> int:
        m = re.search(r"echo-(\d+)", f)
        return int(m.group(1)) if m else 0
    tes = []
    for f in sorted(glob.glob(str(sidecar_path.parent / "*part-phase*MEGRE.json")), key=echo_no):
        try:
            v = json.load(open(f)).get("EchoTime")
        except Exception:  # noqa: BLE001
            v = None
        if v is not None:
            tes.append(float(v))
    if not tes:
        v = json.load(open(sidecar_path)).get("EchoTime")
        tes = [float(v)] if v is not None else []
    return tes


def _sidecar_to_params(path: Path, obj: dict, args, stage: str) -> dict:
    """Map a BIDS MEGRE phase sidecar onto the QSM-CI params.json schema.

    Voxel size is read from the input NIfTI header (the authoritative grid); the sidecar's
    `VoxelSize` is only a fallback. Any explicit acquisition flag the user passed wins.
    """
    consumes = STAGES[stage]["consumes"]
    te = _sidecar_te(path)
    b0 = obj.get("MagneticFieldStrength", 3.0)
    b0_dir = obj.get("B0_dir") or [0.0, 0.0, 1.0]
    voxel = _voxel_size(args, consumes, fallback=obj.get("VoxelSize"))
    if args.te:
        te = args.te
    if args.field_strength is not None:
        b0 = args.field_strength
    if args.b0_dir is not None:
        b0_dir = args.b0_dir
    te = _ensure_te(te, stage)  # BFR/dipole: nominal placeholder if the sidecar carried no TE
    return {"TE": [float(t) for t in te], "B0": float(b0),
            "B0_dir": [float(x) for x in b0_dir], "voxel_size": [float(v) for v in voxel]}
