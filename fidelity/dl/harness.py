#!/usr/bin/env python3
"""Fidelity and first look for the deep-learning originals of QSM.rs's ports (QSMxT/QSM-CI#301).

Each original is a QSM-CI entry (`algorithms/<slug>`) whose pinned image runs the authors' code and
weights. Its QSM.rs port is the `<slug>-qsmrs` entry, which runs the same weights exported to ONNX
through qsmxt. This harness runs entries the way `qsm-ci run` does (the image, run.sh mounted at
/algo, the stage's inputs at /input, no network), with the thread counts fixed, on one case:

  prepare      cut a case to a box of the given size, centred on the mask's bounding box (every
               volume, with the affine moved to the box's corner); params.json is copied.
  determinism  run each original twice; report whether the outputs are bit-identical, and the
               spread if not.
  pair         first look: each original against its QSM.rs port on the same inputs (NRMSE, r and
               max |Δ| inside the mask; Dice for masks). Reported, never a gate.

`--case` is a directory with any of localfield, totalfield, chimap, r2prime, magnitude, phase,
mask (.nii.gz) and params.json. An entry runs only if the case has every input it reads.
`--image` replaces the image of every QSM.rs entry (e.g. a qsmxt build of QSM.rs main with the
weights layer of algorithms/_qsmxt/models.Dockerfile). Results go to <out>/<subcommand>.json and .md.
See fidelity/dl/README.md.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from qsm_ci.containers import _param_env  # noqa: E402  (QSMCI_* env, as qsm-ci run sets it)

PRODUCES = {
    "dipole": ["chimap"], "bfr+dipole": ["chimap"], "end-to-end": ["chimap"],
    "bfr": ["localfield"], "unwrap+bfr": ["localfield"],
    "chi-separation": ["chi-para", "chi-dia"], "brain-extraction": ["mask"],
    "r2prime-generation": ["r2prime"],
}
CONSUMES = {
    "dipole": ["localfield", "mask", "params"], "bfr+dipole": ["totalfield", "mask", "params"],
    "end-to-end": ["phase", "magnitude", "mask", "params"],
    "bfr": ["totalfield", "mask", "params"], "unwrap+bfr": ["phase", "magnitude", "mask", "params"],
    "chi-separation": ["localfield", "r2prime", "chimap", "magnitude", "mask", "params"],
    "brain-extraction": ["magnitude", "params"], "r2prime-generation": ["magnitude", "mask", "params"],
}


# Ports qsmxt exposes only through `qsmxt run` (no subcommand, so no `-qsmrs` entry yet): the
# original is paired with a `qsmxt run` on the case written as a one-subject BIDS dataset, with the
# case's mask supplied, no referencing and no extra corrections. `<slug>:qsmxt-run` in --pairs.
QSMXT_RUN = {
    "iqsm": (["--qsm-algorithm", "iqsm"], "derivatives/qsmxt/sub-1/anat/sub-1_Chimap.nii"),
    "iqsm-plus": (["--qsm-algorithm", "iqsm-plus"], "derivatives/qsmxt/sub-1/anat/sub-1_Chimap.nii"),
    "iqfm": (["--bf-algorithm", "iqfm", "--qsm-algorithm", "tkd"],
             "derivatives/qsmxt/workflow/sub-1/bgremove/sub-1_localfield.nii"),
    "r2primenet": (["--do-r2primemap", "--r2prime-strategy", "r2primenet", "--no-qsm"],
                   "derivatives/qsmxt/sub-1/anat/sub-1_R2primemap.nii"),
}
QSMXT_RUN_COMMON = ["--use-custom-masks", "qsmci", "--qsm-reference", "none",
                    "--no-inhomogeneity-correction", "--no-axial-resampling"]


def manifest(slug: str) -> dict:
    return yaml.safe_load((ROOT / "algorithms" / slug / "algorithm.yml").read_text())


def fname(artifact: str) -> str:
    return "params.json" if artifact == "params" else f"{artifact}.nii.gz"


def load(path):
    import nibabel as nib
    import numpy as np
    return np.asanyarray(nib.load(str(path)).dataobj)


def digest(path) -> str:
    import numpy as np
    a = np.ascontiguousarray(load(path))
    return hashlib.sha256(a.tobytes() + str(a.dtype).encode() + str(a.shape).encode()).hexdigest()


def run_entry(slug: str, case: Path, out: Path, runner: str, threads: int,
              image: "str | None" = None, sets: "dict | None" = None) -> float:
    """Run one entry as `qsm-ci run` would, with the thread counts fixed; return wall seconds."""
    doc = manifest(slug)
    reads = doc.get("inputs") or CONSUMES[doc["stage"]]
    work = out.parent / f".{out.name}-in"
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    for a in reads:
        src = case / fname(a)
        if not src.exists():
            raise FileNotFoundError(f"{slug} reads {a}, which {case} lacks")
        shutil.copy(src, work / fname(a))
    if sets:
        (work / "config.json").write_text(json.dumps(sets))
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)
    env = dict(_param_env(work))
    for k in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "RAYON_NUM_THREADS",
              "TF_NUM_INTRAOP_THREADS", "TF_NUM_INTEROP_THREADS"):
        env[k] = str(threads)
    img = image or doc["image"].split()[0]
    argv = [runner, "run", "--rm", "--network", "none", "--userns=keep-id",
            *[x for k, v in env.items() for x in ("-e", f"{k}={v}")],
            "-v", f"{ROOT / 'algorithms' / slug}:/algo:ro", "-v", f"{work}:/input:ro",
            "-v", f"{out}:/output", img, "bash", "/algo/run.sh"]
    t0 = time.time()
    subprocess.run(argv, check=True)
    dt = time.time() - t0
    shutil.rmtree(work, ignore_errors=True)
    return dt


def run_qsmxt(orig: str, case: Path, out: Path, runner: str, threads: int, image: str) -> float:
    """`qsmxt run` on the case as a BIDS dataset (per-echo MEGRE + sidecars, the mask as a
    derivative); the port's output is written to out/<artifact>.nii.gz."""
    import nibabel as nib
    import numpy as np
    flags, rel = QSMXT_RUN[orig]
    artifact = PRODUCES[manifest(orig)["stage"]][0]
    shutil.rmtree(out, ignore_errors=True)
    bids, res = out / "bids", out / "run"
    anat, der = bids / "sub-1" / "anat", bids / "derivatives" / "qsmci" / "sub-1" / "anat"
    anat.mkdir(parents=True)
    der.mkdir(parents=True)
    res.mkdir()
    p = json.loads((case / "params.json").read_text())
    for part, f in (("phase", "phase"), ("mag", "magnitude")):
        im = nib.load(str(case / f"{f}.nii.gz"))
        a = np.asanyarray(im.dataobj).astype(np.float32)
        for e in range(a.shape[3]):
            stem = anat / f"sub-1_echo-{e + 1}_part-{part}_MEGRE"
            nib.save(nib.Nifti1Image(a[..., e], im.affine), f"{stem}.nii.gz")
            Path(f"{stem}.json").write_text(json.dumps(
                {"EchoTime": p["TE"][e], "MagneticFieldStrength": p["B0"], "EchoNumber": e + 1}))
    shutil.copy(case / "mask.nii.gz", der / "sub-1_mask.nii.gz")
    desc = {"Name": "qsmci", "BIDSVersion": "1.8.0"}
    (bids / "dataset_description.json").write_text(json.dumps(desc))
    (der.parents[1] / "dataset_description.json").write_text(json.dumps({**desc, "GeneratedBy": [{"Name": "qsmci"}]}))
    env = [x for k in ("RAYON_NUM_THREADS", "OMP_NUM_THREADS") for x in ("-e", f"{k}={threads}")]
    argv = [runner, "run", "--rm", "--network", "none", "--userns=keep-id", *env,
            "-v", f"{bids}:/bids:ro", "-v", f"{res}:/out", image,
            "qsmxt", "run", "/bids", "/out", *flags, *QSMXT_RUN_COMMON]
    t0 = time.time()
    subprocess.run(argv, check=True)
    dt = time.time() - t0
    im = nib.load(str(res / rel))
    nib.save(nib.Nifti1Image(np.asanyarray(im.dataobj).astype(np.float32), im.affine), str(out / fname(artifact)))
    return dt


def compare(ref_path: Path, cand_path: Path, mask_path: Path, artifact: str) -> dict:
    import numpy as np
    ref = load(ref_path).astype(np.float64)
    cand = load(cand_path).astype(np.float64)
    if ref.shape != cand.shape:
        return {"error": f"shape {cand.shape} vs {ref.shape}"}
    if artifact == "mask":
        a, b = ref > 0.5, cand > 0.5
        return {"dice": float(2 * (a & b).sum() / max(a.sum() + b.sum(), 1)),
                "voxels_ref": int(a.sum()), "voxels_cand": int(b.sum())}
    m = load(mask_path) > 0
    r, c = ref[m], cand[m]
    d = c - r
    return {"nrmse_pct": float(100 * np.linalg.norm(d) / max(np.linalg.norm(r), 1e-30)),
            "r": float(np.corrcoef(r, c)[0, 1]) if r.std() > 0 and c.std() > 0 else None,
            "max_abs_diff": float(np.abs(d).max()),
            "max_abs_diff_rel_pct": float(100 * np.abs(d).max() / max(np.abs(r).max(), 1e-30)),
            "voxels": int(m.sum())}


def cmd_prepare(args) -> None:
    import nibabel as nib
    import numpy as np
    size = np.array([int(x) for x in args.size.split("x")])
    m = np.asanyarray(nib.load(str(args.case / "mask.nii.gz")).dataobj) > 0
    idx = np.argwhere(m)
    centre = (idx.min(0) + idx.max(0)) // 2
    start = np.clip(centre - size // 2, 0, np.array(m.shape) - size)
    args.out.mkdir(parents=True, exist_ok=True)
    for f in sorted(args.case.glob("*.nii.gz")):
        im = nib.load(str(f))
        a = np.asanyarray(im.dataobj)
        box = a[tuple(slice(int(start[i]), int(start[i] + size[i])) for i in range(3))]
        aff = im.affine.copy()
        aff[:3, 3] = im.affine[:3, :3] @ start + im.affine[:3, 3]
        nib.save(nib.Nifti1Image(np.ascontiguousarray(box), aff, im.header.copy()), str(args.out / f.name))
    if (args.case / "params.json").exists():
        shutil.copy(args.case / "params.json", args.out / "params.json")
    print(f"{args.out}: {tuple(int(x) for x in size)} from {m.shape} at {tuple(int(x) for x in start)}")


def cmd_determinism(args) -> None:
    rows = []
    for slug in args.slugs.split(","):
        doc = manifest(slug)
        outs = PRODUCES[doc["stage"]]
        times, digs = [], []
        try:
            for k in (1, 2):
                d = args.out / "determinism" / slug / f"run{k}"
                times.append(run_entry(slug, args.case, d, args.runner, args.threads,
                                       sets=json.loads(args.set) if args.set else None))
                digs.append({a: digest(d / fname(a)) for a in outs})
        except Exception as e:  # noqa: BLE001
            rows.append({"slug": slug, "error": str(e)})
            continue
        row = {"slug": slug, "image": doc["image"].split()[0], "threads": args.threads,
               "seconds": [round(t, 1) for t in times], "identical": digs[0] == digs[1]}
        if not row["identical"]:
            base = args.out / "determinism" / slug
            row["spread"] = {a: compare(base / "run1" / fname(a), base / "run2" / fname(a),
                                        args.case / "mask.nii.gz", a) for a in outs}
        rows.append(row)
        print(json.dumps(row), flush=True)
    write(args.out, "determinism", rows)


def cmd_pair(args) -> None:
    rows = []
    for pair in args.pairs.split(","):
        ref, cand = pair.split(":") if ":" in pair else (pair, f"{pair}-qsmrs")
        outs = PRODUCES[manifest(ref)["stage"]]
        rdir = args.out / "determinism" / ref / "run1"
        try:
            if not all((rdir / fname(a)).exists() for a in outs):
                rdir = args.out / "pair" / ref
                run_entry(ref, args.case, rdir, args.runner, args.threads)
            cdir = args.out / "pair" / (f"{ref}-qsmxt-run" if cand == "qsmxt-run" else cand)
            if cand == "qsmxt-run":
                t = run_qsmxt(ref, args.case, cdir, args.runner, args.threads, args.image)
            else:
                t = run_entry(cand, args.case, cdir, args.runner, args.threads, image=args.image)
        except Exception as e:  # noqa: BLE001
            rows.append({"reference": ref, "candidate": cand, "error": str(e)})
            continue
        row = {"reference": ref, "candidate": cand, "candidate_image": args.image or
               (None if cand == "qsmxt-run" else manifest(cand)["image"].split()[0]), "candidate_seconds": round(t, 1),
               "metrics": {a: compare(rdir / fname(a), cdir / fname(a), args.case / "mask.nii.gz", a)
                           for a in outs}}
        rows.append(row)
        print(json.dumps(row), flush=True)
    write(args.out, "pair", rows)


def write(out: Path, name: str, rows: list) -> None:
    out.mkdir(parents=True, exist_ok=True)
    p = out / f"{name}.json"
    old = json.loads(p.read_text()) if p.exists() else []
    key = (lambda r: r.get("slug")) if name == "determinism" else \
          (lambda r: (r.get("reference"), r.get("candidate")))
    keep = [r for r in old if key(r) not in {key(x) for x in rows}]
    p.write_text(json.dumps(keep + rows, indent=1) + "\n")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("prepare")
    p.add_argument("--case", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--size", default="128x160x96", help="box XxYxZ in voxels (default %(default)s)")
    for name in ("determinism", "pair"):
        p = sub.add_parser(name)
        p.add_argument("--case", type=Path, required=True)
        p.add_argument("--out", type=Path, required=True)
        p.add_argument("--runner", default="podman")
        p.add_argument("--threads", type=int, default=4)
        if name == "determinism":
            p.add_argument("--slugs", required=True, help="comma-separated originals")
            p.add_argument("--set", help="JSON parameter overrides (config.json), e.g. for a short MoDIP run")
        else:
            p.add_argument("--pairs", required=True,
                           help="comma-separated originals (paired with <slug>-qsmrs), ref:cand, or ref:qsmxt-run")
            p.add_argument("--image", help="image for every QSM.rs entry (default: its algorithm.yml image)")
    args = ap.parse_args()
    args.case, args.out = args.case.resolve(), args.out.resolve()
    {"prepare": cmd_prepare, "determinism": cmd_determinism, "pair": cmd_pair}[args.cmd](args)


if __name__ == "__main__":
    main()
