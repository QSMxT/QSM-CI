#!/usr/bin/env python3
"""Pack the 2026-08-20 MGH bays 4/5 QSM harmonization data into QSM-CI canonical inputs.

The raw drop (data/2026_08_20_bays_4_5_qsm_harmonization) is one subject scanned on two
Siemens 3T scanners (prisma = MAGNETOM Prisma Fit, cima = MAGNETOM Cima.X) with four
protocols (bridge, local, pulseq_online, pulseq_offline) x 3 runs. It is heterogeneous
dcm2niix / offline-recon output: 4D or per-echo 3D volumes, scrambled echo suffixes,
DICOM-scaled or radian phase, and sidecars with no EchoTime (the Pulseq exam cards carry
placeholder timings).

Echo times were recovered from the exam-card PDFs shipped with the data and, for the
Pulseq consensus sequence, from https://github.com/HarmonizedMRI/megre_label:

    bridge (both scanners)   TE 5/11/17/23/29 ms   TR 35 ms  FA 15  (product GRE, R=2)
    prisma local             TE 7.04/13.40/19.76/26.12 ms  TR 31 ms  FA 15  (GRE 2x2, SoS)
    cima local               TE 6.5/12/17.5/23 ms  TR 31 ms  FA 15  (3D-EPI, 2 shots;
                             DICOM echo numbers follow shot order 6.5/17.5/12/23!)
    pulseq on/offline (both) TE 5/11/17/23/29 ms   TR 35 ms  FA 15  (consensus .seq)

For each acquisition this writes
    <out>/<scanner>-<protocol>-<runN>/inputs/{magnitude,phase,mask}.nii.gz + params.json
with echoes reordered to ascending TE, phase in radians, B0 from the scanner carrier
frequency, and B0_dir from the image affine. Source sidecars are patched in place with
the recovered EchoTime (created where missing), and a protocols.json manifest is written
into the raw tree. A magnitude-decay sanity check validates the echo ordering.

Usage:
    python scripts/pack_harmonization.py [--raw DIR] [--out DIR] [--only ID] [--no-mask]

Masks come from SynthStrip (docker: freesurfer/synthstrip) on the first-echo magnitude;
--no-mask skips that step (rerun later to fill in).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import nibabel as nib
import numpy as np

RAW = Path("data/2026_08_20_bays_4_5_qsm_harmonization")
OUT = Path("data/harmonization")

GAMMA_MHZ_PER_T = 42.576384

# Recovered acquisition parameters. TE_ms is listed in DICOM echo-number order (what the
# EchoNumber sidecar field / _eN filename refers to); packing sorts to ascending TE.
TE_SOURCE = "Recovered 2026-08-24 from exam-card PDFs in this dataset and HarmonizedMRI/megre_label"
CONSENSUS_TE = [5.0, 11.0, 17.0, 23.0, 29.0]
PROTOCOLS = {
    ("prisma", "bridge"): dict(TE_ms=CONSENSUS_TE, TR_s=0.035, FA_deg=15,
                               sequence="gre_bridge_1mm_psn_adapt (product GRE, GRAPPA R=2)"),
    ("cima", "bridge"): dict(TE_ms=CONSENSUS_TE, TR_s=0.035, FA_deg=15,
                             sequence="gre_siemens_R2 (product GRE, GRAPPA R=2)"),
    ("prisma", "local"): dict(TE_ms=[7.04, 13.40, 19.76, 26.12], TR_s=0.031, FA_deg=15,
                              sequence="gre_andreas_1mm_psn_sos (product GRE, GRAPPA 2x2, SoS)"),
    ("cima", "local"): dict(TE_ms=[6.5, 17.5, 12.0, 23.0], TR_s=0.031, FA_deg=15,
                            sequence="mesovein_andreas (3D-EPI, CAIPIRINHA 3x2, 2 shots x 2 echoes)"),
    ("prisma", "pulseq_online"): dict(TE_ms=CONSENSUS_TE, TR_s=0.035, FA_deg=15,
                                      sequence="pulseq151fix gre3d_label_spoil_xyzflip_2, Siemens ICE recon"),
    ("prisma", "pulseq_offline"): dict(TE_ms=CONSENSUS_TE, TR_s=0.035, FA_deg=15,
                                       sequence="pulseq151fix gre3d_label_spoil_xyzflip_2, offline GRAPPA recon"),
    ("cima", "pulseq_online"): dict(TE_ms=CONSENSUS_TE, TR_s=0.035, FA_deg=15,
                                    sequence="pulseq151fix_github_megre_R2, Siemens ICE recon"),
    ("cima", "pulseq_offline"): dict(TE_ms=CONSENSUS_TE, TR_s=0.035, FA_deg=15,
                                     sequence="pulseq151fix_github_megre_R2, offline GRAPPA recon"),
}

# Carrier frequency from the exam-card PDFs; B0 = f0 / gamma.
F0_MHZ = {"prisma": 123.243444, "cima": 123.221541}

SCANNER_MODEL = {"prisma": "MAGNETOM Prisma Fit (XR VA30A)", "cima": "MAGNETOM Cima.X (X60 VA61A)"}


def sidecar_for(nii: Path) -> Path | None:
    """dcm2niix sidecar next to the volume, or in a json/ subfolder; None if neither."""
    base = re.sub(r"\.nii(\.gz)?$", "", nii.name)
    for cand in (nii.parent / f"{base}.json", nii.parent / "json" / f"{base}.json"):
        if cand.exists():
            return cand
    return None


def echo_number(nii: Path) -> int:
    """DICOM echo (contrast) number for a volume: filename hints first, else sidecar
    EchoNumber. dcm2niix omits EchoNumber on the first echo of a series -> 1."""
    m = re.search(r"echo(\d+)_", nii.name) or re.search(r"_e(\d)(?:_ph)?\.nii", nii.name) \
        or re.search(r"_ph_(\d)\.nii", nii.name)
    if m:
        return int(m.group(1))
    side = sidecar_for(nii)
    if side:
        num = json.load(open(side)).get("EchoNumber")
        return int(num) if num is not None else 1
    raise SystemExit(f"cannot determine echo number for {nii}")


def phase_to_radians(data: np.ndarray) -> np.ndarray:
    """Handle the three phase encodings present in the drop: radians (offline recon
    float), dcm2niix-scaled int [-4096, 4094], and raw DICOM stored values [0, 4095]."""
    lo, hi = float(np.min(data)), float(np.max(data))
    if hi <= np.pi + 0.01 and lo >= -np.pi - 0.01:
        return data
    if lo < -100:
        return data * np.pi / 4096.0
    if 0 <= lo and hi <= 4095:
        return (data - 2048.0) * np.pi / 2048.0
    raise SystemExit(f"unrecognised phase value range [{lo}, {hi}]")


def is_phase(nii: Path) -> bool:
    return bool(re.search(r"(_ph[a-d]?\.nii|_ph_\d\.nii|_e\d_ph\.nii|phase)", nii.name))


def collect(acq_dir: Path) -> tuple[dict[int, Path], dict[int, Path]]:
    """Map echo number -> volume for magnitude and phase; splits a single 4D magnitude."""
    niis = sorted(p for p in acq_dir.iterdir() if re.search(r"\.nii(\.gz)?$", p.name))
    mags = {}
    phases = {}
    for p in niis:
        (phases if is_phase(p) else mags)[echo_number(p)] = p
    return mags, phases


def patch_sidecar(nii: Path, te_s: float, extra: dict | None = None) -> None:
    side = sidecar_for(nii)
    if side is None:
        side = nii.parent / (re.sub(r"\.nii(\.gz)?$", "", nii.name) + ".json")
        payload = {}
    else:
        payload = json.load(open(side))
    payload["EchoTime"] = round(te_s, 6)
    payload["EchoTimeSource"] = TE_SOURCE
    payload.update(extra or {})
    side.write_text(json.dumps(payload, indent=2) + "\n")


def b0_dir_from_affine(affine: np.ndarray) -> list[float]:
    """B0 lies along scanner z (superior, +z in RAS); express it in voxel axes."""
    rot = affine[:3, :3] / np.linalg.norm(affine[:3, :3], axis=0)
    direction = rot.T @ np.array([0.0, 0.0, 1.0])
    direction /= np.linalg.norm(direction)
    return [round(float(v), 6) for v in direction]


def load_echo(path: Path, echo_4d: int | None = None):
    img = nib.load(str(path))
    data = np.asanyarray(img.dataobj).astype(np.float64)
    if data.ndim == 4:
        if echo_4d is None:
            raise SystemExit(f"{path} is 4D but no echo index requested")
        data = data[..., echo_4d]
    return data, img.affine


def pack_acquisition(scanner: str, protocol: str, run: str, out_root: Path) -> dict | None:
    acq_dir = RAW / scanner / protocol / run
    proto = PROTOCOLS[(scanner, protocol)]
    te_by_echonum = proto["TE_ms"]
    n_echoes = len(te_by_echonum)
    acq_id = f"{scanner}-{protocol.replace('_', '-')}-{run}"

    mags, phases = collect(acq_dir)

    # A single 4D magnitude series (prisma product exports) covers all echoes.
    mag_4d = None
    if len(mags) == 1 and nib.load(str(next(iter(mags.values())))).ndim == 4:
        mag_4d = next(iter(mags.values()))
        mags = {e + 1: mag_4d for e in range(n_echoes)}
    if set(mags) != set(range(1, n_echoes + 1)) or set(phases) != set(range(1, n_echoes + 1)):
        print(f"  !! {acq_id}: incomplete echoes (mag {sorted(mags)}, phase {sorted(phases)}) — skipped")
        return None

    order = np.argsort(te_by_echonum)  # echo numbers (0-based) in ascending-TE order
    tes_sorted = [round(te_by_echonum[i] / 1000.0, 6) for i in order]

    mag_vols, phase_vols, affine = [], [], None
    for idx in order:
        echo = int(idx) + 1
        m, aff_m = load_echo(mags[echo], echo_4d=idx if mag_4d else None)
        p, aff_p = load_echo(phases[echo])
        affine = aff_m if affine is None else affine
        for aff in (aff_m, aff_p):
            if not np.allclose(aff, affine, atol=1e-3):
                raise SystemExit(f"{acq_id}: affine mismatch across echo volumes")
        mag_vols.append(m)
        phase_vols.append(phase_to_radians(p))

    mag = np.stack(mag_vols, axis=-1)
    phase = np.stack(phase_vols, axis=-1)

    # Sanity: within bright tissue, magnitude must decay monotonically with TE.
    bright = mag[..., 0] > np.percentile(mag[..., 0], 60)
    decay = [float(mag[..., e][bright].mean()) for e in range(n_echoes)]
    monotone = all(decay[i] > decay[i + 1] for i in range(n_echoes - 1))
    if not monotone:
        print(f"  !! {acq_id}: magnitude decay NOT monotone {['%.1f' % d for d in decay]} — check echo order")

    f0 = F0_MHZ[scanner]
    params = {
        "TE": tes_sorted,
        "B0": round(f0 / GAMMA_MHZ_PER_T, 4),
        "B0_dir": b0_dir_from_affine(affine),
        "voxel_size": [round(float(v), 4) for v in nib.affines.voxel_sizes(affine)],
        "B0_nominal": 3.0,
        "f0_MHz": f0,
        "TR": proto["TR_s"],
        "flip_angle": proto["FA_deg"],
        "scanner": SCANNER_MODEL[scanner],
        "protocol": protocol,
        "run": run,
        "sequence": proto["sequence"],
        "TE_source": TE_SOURCE,
    }

    out = out_root / acq_id / "inputs"
    out.mkdir(parents=True, exist_ok=True)
    nib.save(nib.Nifti1Image(mag.astype(np.float32), affine), str(out / "magnitude.nii.gz"))
    nib.save(nib.Nifti1Image(phase.astype(np.float32), affine), str(out / "phase.nii.gz"))
    (out / "params.json").write_text(json.dumps(params, indent=2) + "\n")

    # Write recovered TEs back into the source sidecars (create where dcm2niix left none).
    if mag_4d:
        patch_sidecar(mag_4d, tes_sorted[0], {"EchoTimes": tes_sorted})
    for echo, nii in {**({} if mag_4d else mags), **phases}.items():
        patch_sidecar(nii, te_by_echonum[echo - 1] / 1000.0)

    print(f"  {acq_id}: {mag.shape} TEs {['%.2f' % (t * 1000) for t in tes_sorted]} ms, "
          f"decay {'ok' if monotone else 'BAD'}")
    return {"id": acq_id, "scanner": scanner, "protocol": protocol, "run": run,
            "shape": list(mag.shape), "decay_mean": decay, "monotone_decay": monotone, **params}


def synthstrip_mask(acq_out: Path) -> None:
    """Brain mask from SynthStrip (docker) on the first-echo magnitude."""
    mask_path = acq_out / "inputs" / "mask.nii.gz"
    if mask_path.exists():
        return
    mag = nib.load(str(acq_out / "inputs" / "magnitude.nii.gz"))
    e1 = acq_out / "inputs" / "_e1_tmp.nii.gz"
    nib.save(nib.Nifti1Image(np.asanyarray(mag.dataobj)[..., 0].astype(np.float32), mag.affine), str(e1))
    try:
        subprocess.run(
            ["docker", "run", "--rm", "--user", f"{os.getuid()}:{os.getgid()}",
             "-v", f"{acq_out.resolve() / 'inputs'}:/data",
             "freesurfer/synthstrip", "-i", "/data/_e1_tmp.nii.gz", "-m", "/data/mask.nii.gz"],
            check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as err:
        print(f"  !! synthstrip failed for {acq_out.name}: {err.stderr[-500:]}")
        return
    finally:
        e1.unlink(missing_ok=True)
    # binarise (synthstrip writes 0/1 already, but be safe) and drop stray values
    m = nib.load(str(mask_path))
    data = (np.asanyarray(m.dataobj) > 0.5).astype(np.uint8)
    nib.save(nib.Nifti1Image(data, m.affine), str(mask_path))
    print(f"  {acq_out.name}: mask {int(data.sum())} voxels")


def main() -> None:
    global RAW
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--raw", type=Path, default=RAW)
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--only", help="pack a single acquisition id, e.g. prisma-bridge-run1")
    ap.add_argument("--no-mask", action="store_true", help="skip SynthStrip masking")
    args = ap.parse_args()
    RAW = args.raw

    manifest = []
    for scanner in ("prisma", "cima"):
        for protocol in ("bridge", "local", "pulseq_online", "pulseq_offline"):
            proto_dir = RAW / scanner / protocol
            if not proto_dir.is_dir():
                continue
            for run_dir in sorted(proto_dir.iterdir()):
                if not run_dir.is_dir():
                    continue
                acq_id = f"{scanner}-{protocol.replace('_', '-')}-{run_dir.name}"
                if args.only and acq_id != args.only:
                    continue
                entry = pack_acquisition(scanner, protocol, run_dir.name, args.out)
                if entry:
                    manifest.append(entry)

    (RAW / "protocols.json").write_text(json.dumps({
        "description": "Recovered acquisition parameters for the 2026-08-20 MGH bays 4/5 "
                       "QSM harmonization dataset (one subject, two scanners, four protocols, three runs)",
        "TE_source": TE_SOURCE,
        "acquisitions": manifest,
    }, indent=2) + "\n")

    if not args.no_mask:
        for entry in manifest:
            synthstrip_mask(args.out / entry["id"])

    print(f"\npacked {len(manifest)} acquisitions -> {args.out}")


if __name__ == "__main__":
    main()
