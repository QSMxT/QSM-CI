#!/usr/bin/env python3
"""Pack the EMTP 2026 traveling-head QSM data into QSM-CI canonical inputs.

The raw drop (Xu Li, KKI; "03_Analysis_Shared") is six subjects, each scanned at KKI on Philips
and some also at other sites, with the shared `bridge` protocol and each site's `local` protocol
x 3 runs. It is dcm2niix output, one 3D volume per echo with complete sidecars:

    <subject>/<session>/run{1,2,3}/{bridge,local}/*_e<N>.nii.gz           magnitude
                                                  *_e<N>_ph.nii.gz        phase (Philips, Siemens)
                                                  *_e<N>_{real,imaginary}.nii.gz   (GE)

Folder names carry subject initials, so nothing from them is published: subjects are renamed to
the numeric part of their folder (`005001_XX` -> `s005001`) and scanners to a site-model tag.

For each acquisition this writes
    <out>/<subject>-<scanner>-<protocol>-<runN>/inputs/{magnitude,phase,mask}.nii.gz + params.json
with echoes in ascending TE, phase in radians, B0 from the sidecar imaging frequency and B0_dir
from the image affine. GE real/imaginary pairs are combined into magnitude and phase after undoing
GE's alternate-slice pi modulation (see `ge_complex_to_phase`).

Usage:
    python scripts/pack_emtp.py --raw DIR [--out DIR] [--only ID] [--no-mask]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import nibabel as nib
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pack_harmonization import GAMMA_MHZ_PER_T, b0_dir_from_affine, hdbet_mask, phase_to_radians  # noqa: E402

OUT = Path("data/harmonization")

# (Manufacturer, ManufacturersModelName, InstitutionName) -> scanner tag used in acquisition ids.
SCANNERS = {
    ("Philips", "Achieva dStream", "Kennedy Krieger Institute"): "kki-achieva",
    ("Philips", "Ingenia Elition X", "Kennedy Krieger Institute"): "kki-elition",
    ("GE", "DISCOVERY MR750", "CBIC"): "cbic-mr750",
    ("Siemens", "MAGNETOM Prisma Fit", "Weill Medical College-Cornell"): "cbic-prisma",
    ("Siemens", "MAGNETOM Skyra", "UMass Life Science Lab"): "umass-skyra",
    ("Philips", "Ingenia", "Hamburg"): "hamburg-ingenia",
}
SITE_LABEL = {
    "kki-achieva": "KKI", "kki-elition": "KKI", "cbic-mr750": "Weill Cornell CBIC",
    "cbic-prisma": "Weill Cornell CBIC", "umass-skyra": "UMass", "hamburg-ingenia": "Hamburg",
}
# Multiplier taking each vendor's stored phase to QSM-CI's convention (paramagnetic = positive
# chi after the standard pipeline). Checked per vendor on the same subjects across sites: GE
# frequency maps anticorrelate with the same subject's Siemens and Philips maps, so GE is negated.
PHASE_SIGN = {"Philips": 1.0, "Siemens": 1.0, "GE": -1.0}

ECHO_RE = re.compile(r"_e(\d+)(?:_(ph|real|imaginary))?\.nii\.gz$")


def subject_id(folder: str) -> str:
    m = re.match(r"(\d+)_", folder)
    if not m:
        raise SystemExit(f"subject folder {folder!r} has no numeric id")
    return f"s{m.group(1)}"


def collect(acq_dir: Path) -> dict[str, dict[int, Path]]:
    """Map part ('mag', 'ph', 'real', 'imaginary') -> echo number -> per-echo volume. The 4D
    *_GRE_{mag,phase} files are stacks of the same echoes and are ignored."""
    parts: dict[str, dict[int, Path]] = {}
    for p in sorted(acq_dir.glob("*.nii.gz")):
        m = ECHO_RE.search(p.name)
        if m:
            parts.setdefault(m.group(2) or "mag", {})[int(m.group(1))] = p
    return parts


def sidecar(nii: Path) -> dict:
    return json.loads(nii.with_name(nii.name.replace(".nii.gz", ".json")).read_text())


def load(path: Path) -> tuple[np.ndarray, np.ndarray]:
    img = nib.load(str(path))
    return np.asanyarray(img.dataobj).astype(np.float64), img.affine


def chop_axis(z: np.ndarray) -> int | None:
    """The axis along which neighbouring voxels' phase differs by ~pi (GE's (-1)^k slice
    modulation), from the circular mean of masked neighbour phase differences; None if absent."""
    mask = np.abs(z) > np.percentile(np.abs(z), 75)
    for ax in range(3):
        a, w = np.moveaxis(z, ax, -1), np.moveaxis(mask, ax, -1)
        d = a[..., 1:] * np.conj(a[..., :-1])
        valid = w[..., 1:] & w[..., :-1]
        if np.abs(np.angle(np.mean(d[valid] / np.abs(d[valid])))) > np.pi / 2:
            return ax
    return None


def ge_complex_to_phase(reals: list[np.ndarray], imags: list[np.ndarray]) -> tuple[list[np.ndarray], int | None]:
    """Phase per echo from GE real/imaginary, with the alternate-slice pi flip removed. The chop
    axis is detected on the first echo and applied to all echoes so they stay consistent."""
    zs = [r + 1j * i for r, i in zip(reals, imags)]
    ax = chop_axis(zs[0])
    if ax is not None:
        shape = [1, 1, 1]
        shape[ax] = zs[0].shape[ax]
        sign = ((-1.0) ** np.arange(zs[0].shape[ax])).reshape(shape)
        zs = [z * sign for z in zs]
    return [np.angle(z) for z in zs], ax


def pack_acquisition(acq_dir: Path, subject: str, protocol: str, run: str, out_root: Path,
                     only: str | None, skip_existing: bool = False) -> dict | None:
    parts = collect(acq_dir)
    mags = parts.get("mag", {})
    meta = sidecar(mags[min(mags)])
    vendor = meta["Manufacturer"]
    scanner = SCANNERS[(vendor, meta["ManufacturersModelName"], meta["InstitutionName"])]
    acq_id = f"{subject}-{scanner}-{protocol}-{run}"
    if only and acq_id != only:
        return None
    if skip_existing and (out_root / acq_id / "inputs" / "params.json").exists():
        return {"id": acq_id, **json.loads((out_root / acq_id / "inputs" / "params.json").read_text())}

    echoes = sorted(mags, key=lambda e: sidecar(mags[e])["EchoTime"])
    tes = [round(sidecar(mags[e])["EchoTime"], 6) for e in echoes]
    complex_input = "real" in parts
    phase_part = ("real", "imaginary") if complex_input else ("ph",)
    for part in phase_part:
        if set(parts.get(part, {})) != set(mags):
            print(f"  !! {acq_id}: {part} echoes {sorted(parts.get(part, {}))} != magnitude {sorted(mags)} — skipped")
            return None

    affine = None
    mag_vols, raw = [], {part: [] for part in phase_part}
    for e in echoes:
        for part, vols in [("mag", mag_vols), *[(p, raw[p]) for p in phase_part]]:
            data, aff = load(parts[part][e])
            affine = aff if affine is None else affine
            if not np.allclose(aff, affine, atol=1e-3):
                raise SystemExit(f"{acq_id}: affine mismatch across echo volumes")
            vols.append(data)

    chop = None
    if complex_input:
        phase_vols, chop = ge_complex_to_phase(raw["real"], raw["imaginary"])
    else:
        phase_vols = [phase_to_radians(p) for p in raw["ph"]]
    mag = np.stack(mag_vols, axis=-1)
    phase = np.stack(phase_vols, axis=-1) * PHASE_SIGN[vendor]

    bright = mag[..., 0] > np.percentile(mag[..., 0], 60)
    decay = [float(mag[..., i][bright].mean()) for i in range(len(echoes))]
    monotone = all(decay[i] > decay[i + 1] for i in range(len(decay) - 1))
    if not monotone:
        print(f"  !! {acq_id}: magnitude decay NOT monotone {['%.1f' % d for d in decay]} — check echo order")

    f0 = float(meta["ImagingFrequency"])
    params = {
        "TE": tes,
        "B0": round(f0 / GAMMA_MHZ_PER_T, 4),
        "B0_dir": b0_dir_from_affine(affine),
        "voxel_size": [round(float(v), 4) for v in nib.affines.voxel_sizes(affine)],
        "B0_nominal": float(meta["MagneticFieldStrength"]),
        "f0_MHz": f0,
        "TR": round(float(meta["RepetitionTime"]), 6),
        "flip_angle": meta["FlipAngle"],
        "subject": subject,
        "site": SITE_LABEL[scanner],
        "vendor": vendor,
        "scanner": f"{meta['ManufacturersModelName']} ({meta.get('SoftwareVersions', '?')})",
        "protocol": protocol,
        "run": run,
        "sequence": meta.get("SeriesDescription", ""),
        "phase_source": "real/imaginary" + (f", alternate-slice pi flip removed on axis {chop}" if chop is not None else "")
                        if complex_input else "phase",
        "TE_source": "dcm2niix sidecars",
    }

    out = out_root / acq_id / "inputs"
    out.mkdir(parents=True, exist_ok=True)
    nib.save(nib.Nifti1Image(mag.astype(np.float32), affine), str(out / "magnitude.nii.gz"))
    nib.save(nib.Nifti1Image(phase.astype(np.float32), affine), str(out / "phase.nii.gz"))
    (out / "params.json").write_text(json.dumps(params, indent=2) + "\n")
    print(f"  {acq_id}: {mag.shape} TEs {['%.2f' % (t * 1000) for t in tes]} ms, "
          f"decay {'ok' if monotone else 'BAD'}" + (f", chop axis {chop}" if complex_input else ""))
    return {"id": acq_id, "shape": list(mag.shape), "monotone_decay": monotone, **params}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--raw", type=Path, required=True, help="the 03_Analysis_Shared folder")
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--only", help="pack a single acquisition id, e.g. s002001-kki-achieva-bridge-run1")
    ap.add_argument("--no-mask", action="store_true", help="skip HD-BET masking")
    ap.add_argument("--skip-existing", action="store_true",
                    help="keep acquisitions that already have a params.json (masks are still filled in)")
    ap.add_argument("--qsm-ci", default="qsm-ci",
                    help="qsm-ci executable used to run the hd-bet-qsmci masking stage")
    ap.add_argument("--runner", help="container runner for masking (qsm-ci run --runner), e.g. apptainer")
    args = ap.parse_args()

    manifest = []
    for acq_dir in sorted(args.raw.glob("*/*/run*/*")):
        if not acq_dir.is_dir():
            continue
        subj_dir, _session, run, protocol = acq_dir.relative_to(args.raw).parts
        entry = pack_acquisition(acq_dir, subject_id(subj_dir), protocol, run, args.out, args.only,
                                 args.skip_existing)
        if entry:
            manifest.append(entry)

    if not args.only:  # a single-acquisition run (one array task) must not clobber the full manifest
        (args.out / "emtp_manifest.json").write_text(json.dumps({
            "description": "EMTP 2026 traveling-head QSM dataset (6 subjects, KKI Philips plus "
                           "traveling sessions on GE, Siemens and Philips; bridge + local x 3 runs)",
            "acquisitions": manifest,
        }, indent=2) + "\n")

    if not args.no_mask:
        for entry in manifest:
            hdbet_mask(args.out / entry["id"], args.qsm_ci, args.runner)

    print(f"\npacked {len(manifest)} acquisitions -> {args.out}")


if __name__ == "__main__":
    main()
