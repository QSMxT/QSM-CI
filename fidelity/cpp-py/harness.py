#!/usr/bin/env python3
"""Fidelity and first look for the C++ and Python originals of QSM.rs's ports (QSMxT/QSM-CI#302).

These originals are not QSM-CI stages (N4, Gibbs removal, MP-PCA, best-path unwrapping) or, for
BET, cannot be published (see algorithms/_bet2/README.md), so they run here as *fixture runs*: each
original's pinned image is run on fixed inputs through a thin call script, and nothing is scored.

  prepare      cut a case (a QSM-CI input dir: phase, magnitude, mask) into the fixture inputs:
               mag1 (echo-1 magnitude), phase1 (echo-1 wrapped phase), mag4d (all echoes) and
               mask3d, as float32/uint8 NIfTI.
  determinism  run each original's image twice; the outputs must be bit-identical.
  host         run the same call scripts outside the container, with the same pinned packages
               (`--python`: a Python 3.12 with requirements.lock; `--n4-bin`: the same ANTs
               release binary; `--bet2-bin`: bet2 built from the same commit); compared with the
               image run, bit for bit.
  pair         first look: each original against QSM.rs's port (fidelity/cpp-py/qsmrs-probe, and
               `qsmxt homogeneity --method n4` in a qsmxt image), on the same inputs. Reported,
               never a gate.

Results go to <out>/<subcommand>.json and .md. See fidelity/cpp-py/README.md.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ANTS_IMAGE = ("ghcr.io/astewartau/qsm-ci/ants-n4@sha256:"   # v1
              "621644e172c4872f1d181c9c18dc8717c40aece19de8d28c31fce93028017c49")
PY_IMAGE = ("ghcr.io/astewartau/qsm-ci/py-originals@sha256:"   # v1
            "7654140b9e7ff00552590d945db9b8d52c526fd01b8e36d5e1ad524b02b510ed")
BET_IMAGE = "localhost/qsm-ci/bet2:d5acd7f"   # local only (algorithms/_bet2/README.md)
PRELUDE_IMAGE = "localhost/qsm-ci/fsl-prelude:2603.0"   # local only (algorithms/_fsl-prelude)

# Each fixture run: the image, the folder mounted at /algo, the command (paths under /in, /out),
# and the outputs it writes. `needs` names an earlier run whose output becomes an input.
OPS = {
    "n4": {
        "image": ANTS_IMAGE, "algo": "algorithms/_ants",
        "cmd": ["bash", "{algo}/n4.sh", "{in}/mag1.nii.gz", "{out}/n4.nii.gz", "{out}/n4_bias.nii.gz"],
        "outputs": ["n4.nii.gz", "n4_bias.nii.gz"],
    },
    "bestpath": {
        "image": PY_IMAGE, "algo": "algorithms/_python-originals",
        "cmd": ["python", "{algo}/bestpath.py", "{in}/phase1.nii.gz", "{out}/bestpath.nii.gz",
                "--mask", "{in}/mask3d.nii.gz"],
        "outputs": ["bestpath.nii.gz"],
    },
    "gibbs": {
        "image": PY_IMAGE, "algo": "algorithms/_python-originals",
        "cmd": ["python", "{algo}/gibbs.py", "{in}/mag4d.nii.gz", "{out}/gibbs.nii.gz"],
        "outputs": ["gibbs.nii.gz"],
    },
    "mppca": {
        "image": PY_IMAGE, "algo": "algorithms/_python-originals",
        "cmd": ["python", "{algo}/mppca.py", "{in}/mag4d.nii.gz", "{out}/mppca.nii.gz",
                "--mask", "{in}/mask3d.nii.gz"],
        "outputs": ["mppca.nii.gz"],
    },
    # FSL prelude on the echo-1 phase: `-f` is full 3-D (the report's algorithm, QSM.rs's port) at
    # QSM.rs's 6 partitions; `prelude-fsl-defaults` is FSL's own defaults (8 partitions, regions
    # labelled slice by slice, merged in 3-D), which QSM.rs does not implement.
    "prelude": {
        "image": PRELUDE_IMAGE, "algo": "algorithms/_fsl-prelude",
        "cmd": ["bash", "{algo}/prelude.sh", "{in}/phase1.nii.gz", "{in}/mag1.nii.gz",
                "{in}/mask3d.nii.gz", "{out}/prelude", "-f", "-n", "6"],
        "outputs": ["prelude.nii.gz"],
    },
    "prelude-fsl-defaults": {
        "image": PRELUDE_IMAGE, "algo": "algorithms/_fsl-prelude",
        "cmd": ["bash", "{algo}/prelude.sh", "{in}/phase1.nii.gz", "{in}/mag1.nii.gz",
                "{in}/mask3d.nii.gz", "{out}/prelude_defaults"],
        "outputs": ["prelude_defaults.nii.gz"],
    },
    # QSMART's brainmask.m: bet2 -f 0.2 on the N4-corrected echo-1 magnitude. The N4 output is the
    # original's (ANTs), so BET is compared from the same input.
    "bet-f0.2": {
        "image": BET_IMAGE, "algo": "algorithms/_bet2",
        "cmd": ["bash", "{algo}/bet.sh", "{in}/mag1_n4.nii.gz", "{out}/bet02", "-f", "0.2"],
        "outputs": ["bet02_mask.nii.gz"],
    },
    "bet-f0.5": {
        "image": BET_IMAGE, "algo": "algorithms/_bet2",
        "cmd": ["bash", "{algo}/bet.sh", "{in}/mag1_n4.nii.gz", "{out}/bet05"],
        "outputs": ["bet05_mask.nii.gz"],
    },
}


def load(path):
    import nibabel as nib
    import numpy as np
    return np.asanyarray(nib.load(str(path)).dataobj)


def digest(path) -> str:
    import numpy as np
    a = np.ascontiguousarray(load(path))
    return hashlib.sha256(a.tobytes() + str(a.dtype).encode() + str(a.shape).encode()).hexdigest()


def run_image(op: str, case: Path, out: Path, runner: str, image: "str | None" = None) -> float:
    spec = OPS[op]
    out.mkdir(parents=True, exist_ok=True)
    fmt = {"algo": "/algo", "in": "/in", "out": "/out"}
    argv = [runner, "run", "--rm", "--network", "none",
            "-v", f"{ROOT / spec['algo']}:/algo:ro", "-v", f"{case}:/in:ro", "-v", f"{out}:/out",
            image or spec["image"]] + [c.format(**fmt) for c in spec["cmd"]]
    t0 = time.time()
    subprocess.run(argv, check=True)
    return time.time() - t0


def run_host(op: str, case: Path, out: Path, python: str, n4_bin: str, bet2_bin: str) -> float:
    spec = OPS[op]
    out.mkdir(parents=True, exist_ok=True)
    fmt = {"algo": str(ROOT / spec["algo"]), "in": str(case), "out": str(out)}
    argv = [c.format(**fmt) for c in spec["cmd"]]
    env = dict(os.environ, OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1",
               ITK_GLOBAL_DEFAULT_NUMBER_OF_THREADS="4", N4_BIN=n4_bin, BET2_BIN=bet2_bin)
    if argv[0] == "python":
        argv[0] = python
    t0 = time.time()
    subprocess.run(argv, check=True, env=env)
    return time.time() - t0


def ops_from(arg: str) -> list:
    ops = list(OPS) if arg == "all" else arg.split(",")
    bad = [o for o in ops if o not in OPS]
    if bad:
        raise SystemExit(f"unknown op(s): {', '.join(bad)} (known: {', '.join(OPS)})")
    return ops


def write(out: Path, name: str, rows: list, md: str) -> None:
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{name}.json").write_text(json.dumps(rows, indent=2) + "\n")
    (out / f"{name}.md").write_text(md)
    print(md)


# ------------------------------------------------------------------------------------------------

def cmd_prepare(a) -> int:
    import nibabel as nib
    import numpy as np
    src, dst = Path(a.case), Path(a.out)
    dst.mkdir(parents=True, exist_ok=True)
    mag, ph, mk = (nib.load(str(src / f)) for f in ("magnitude.nii.gz", "phase.nii.gz", "mask.nii.gz"))

    def save(arr, name, ref, dtype=np.float32):
        h = ref.header.copy()
        h.set_data_dtype(dtype)
        h.set_slope_inter(1, 0)
        nib.save(nib.Nifti1Image(np.asarray(arr, dtype=dtype), ref.affine, h), str(dst / name))

    M = np.asarray(mag.dataobj, dtype=np.float32)
    P = np.asarray(ph.dataobj, dtype=np.float32)
    M = M if M.ndim == 4 else M[..., None]
    P = P if P.ndim == 4 else P[..., None]
    save(M[..., 0], "mag1.nii.gz", mag)
    save(P[..., 0], "phase1.nii.gz", ph)
    save(M, "mag4d.nii.gz", mag)
    save(np.asarray(mk.dataobj) > 0, "mask3d.nii.gz", mk, np.uint8)
    print(f"prepared {dst}: {M.shape[:3]}, {M.shape[3]} echo(es), "
          f"{int((np.asarray(mk.dataobj) > 0).sum())} mask voxels")
    return 0


def _bet_input(case: Path, work: Path, runner: str) -> None:
    """BET reads the original N4's output of mag1 (QSMART's order): run ANTs once into the case."""
    if (case / "mag1_n4.nii.gz").exists():
        return
    tmp = work / "_n4_for_bet"
    run_image("n4", case, tmp, runner)
    shutil.copy(tmp / "n4.nii.gz", case / "mag1_n4.nii.gz")


def cmd_determinism(a) -> int:
    case, out = Path(a.case).resolve(), Path(a.out).resolve()
    rows = []
    for op in ops_from(a.ops):
        if op.startswith("bet"):
            _bet_input(case, out, a.runner)
        t = [run_image(op, case, out / "determinism" / op / f"run{i}", a.runner) for i in (1, 2)]
        for f in OPS[op]["outputs"]:
            d = [digest(out / "determinism" / op / f"run{i}" / f) for i in (1, 2)]
            rows.append({"op": op, "output": f, "image": OPS[op]["image"], "identical": d[0] == d[1],
                         "sha256": d[0], "runtime_s": [round(x, 1) for x in t]})
    md = ["| original | output | image twice | run time, s |", "|---|---|---|---|"]
    md += [f"| `{r['op']}` | `{r['output']}` | {'identical' if r['identical'] else '**differs**'} | "
           f"{r['runtime_s'][0]} / {r['runtime_s'][1]} |" for r in rows]
    write(out, "determinism", rows, "\n".join(md) + "\n")
    return 0 if all(r["identical"] for r in rows) else 1


def cmd_host(a) -> int:
    case, out = Path(a.case).resolve(), Path(a.out).resolve()
    rows = []
    for op in ops_from(a.ops):
        if (op.startswith("bet") and not a.bet2_bin) or op.startswith("prelude"):
            continue   # bet2 needs --bet2-bin; prelude is FSL's own binary, with no host build
        if op.startswith("bet"):
            _bet_input(case, out, a.runner)
        img = out / "determinism" / op / "run1"
        if not all((img / f).exists() for f in OPS[op]["outputs"]):
            run_image(op, case, img, a.runner)
        t = run_host(op, case, out / "host" / op, a.python, a.n4_bin, a.bet2_bin or "bet2")
        for f in OPS[op]["outputs"]:
            di, dh = digest(img / f), digest(out / "host" / op / f)
            rows.append({"op": op, "output": f, "identical": di == dh, "runtime_s": round(t, 1)})
    md = ["| original | output | image vs host | host run time, s |", "|---|---|---|---|"]
    md += [f"| `{r['op']}` | `{r['output']}` | {'identical' if r['identical'] else '**differs**'} | "
           f"{r['runtime_s']} |" for r in rows]
    write(out, "host", rows, "\n".join(md) + "\n")
    return 0 if all(r["identical"] for r in rows) else 1


# ------------------------------------------------------------------------------------------------
# First look against QSM.rs

def compare(ref, cand, mask) -> dict:
    """Agreement of `cand` with `ref` inside `mask` (broadcast over a 4th axis): NRMSE %
    (‖cand − ref‖ / ‖ref‖), correlation, max and 99th-percentile |Δ|, max |Δ| relative to max |ref|."""
    import numpy as np
    ref, cand = np.asarray(ref, float), np.asarray(cand, float)
    m = np.asarray(mask) > 0
    if ref.ndim == 4:
        m = np.broadcast_to(m[..., None], ref.shape)
    r, c = ref[m], cand[m]
    d = c - r
    ad = np.abs(d)
    return {"nrmse": float(100 * np.linalg.norm(d) / np.linalg.norm(r)) if np.linalg.norm(r) else 0.0,
            "correlation": float(np.corrcoef(r, c)[0, 1]) if r.std() and c.std() else 1.0,
            "max_abs": float(ad.max()), "p99_abs": float(np.percentile(ad, 99)),
            "max_rel": float(ad.max() / np.abs(r).max()) if np.abs(r).max() else 0.0,
            "identical_frac": float((d == 0).mean()), "voxels": int(m.sum())}


def dice(a, b) -> dict:
    import numpy as np
    a, b = np.asarray(a) > 0, np.asarray(b) > 0
    return {"dice": float(2 * (a & b).sum() / (a.sum() + b.sum())), "n_ref": int(a.sum()),
            "n_cand": int(b.sum()), "differ": int((a ^ b).sum())}


def wraps(ref, cand, mask) -> dict:
    """Best-path: which in-mask voxels agree exactly, and which differ by a whole number of 2π
    (the arbitrary offset of a connected component), after removing the most common offset."""
    import numpy as np
    m = np.asarray(mask) > 0
    d = (np.asarray(cand, float) - np.asarray(ref, float))[m]
    k = np.round(d / (2 * np.pi))
    vals, counts = np.unique(k, return_counts=True)
    k0 = vals[np.argmax(counts)]
    resid = d - k * 2 * np.pi
    return {"identical_frac": float((d == 0).mean()), "same_wrap_frac": float((k == k0).mean()),
            "global_offset_2pi": int(k0), "max_abs_off_2pi": float(np.abs(resid).max()),
            "voxels": int(m.sum())}


def probe(a, *args) -> float:
    env = dict(os.environ, RAYON_NUM_THREADS=str(a.threads))
    t0 = time.time()
    subprocess.run([a.probe, *map(str, args)], check=True, env=env)
    return time.time() - t0


def cmd_pair(a) -> int:
    case, out = Path(a.case).resolve(), Path(a.out).resolve()
    ref = out / "determinism"
    cand = out / "pair"
    cand.mkdir(parents=True, exist_ok=True)
    mask = load(case / "mask3d.nii.gz")
    rows = []

    def need(op):
        if not all((ref / op / "run1" / f).exists() for f in OPS[op]["outputs"]):
            if op.startswith("bet"):
                _bet_input(case, out, a.runner)
            run_image(op, case, ref / op / "run1", a.runner)
        return ref / op / "run1"

    ops = ops_from(a.ops)
    if "n4" in ops:
        r = need("n4")
        t = probe(a, "n4", case / "mag1.nii.gz", cand / "n4.nii.gz", cand / "n4_bias.nii.gz")
        head = load(case / "mag1.nii.gz") > 0
        for f in ("n4.nii.gz", "n4_bias.nii.gz"):
            rows.append({"op": "n4", "port": "qsm_core::utils::n4 (probe)", "settings": "defaults",
                         "output": f, "runtime_s": round(t, 1),
                         "in_mask": compare(load(r / f), load(cand / f), mask),
                         "where_input_gt_0": compare(load(r / f), load(cand / f), head)})
        if a.qsmxt_image:
            qo = cand / "qsmxt"
            qo.mkdir(exist_ok=True)
            t0 = time.time()
            subprocess.run([a.runner, "run", "--rm", "--network", "none", "-e",
                            f"RAYON_NUM_THREADS={a.threads}", "-v", f"{case}:/in:ro", "-v",
                            f"{qo}:/out", "--entrypoint", "qsmxt", a.qsmxt_image, "homogeneity",
                            "/in/mag1.nii.gz", "-o", "/out/n4.nii.gz", "--method", "n4"], check=True)
            rows.append({"op": "n4", "port": f"qsmxt homogeneity --method n4 ({a.qsmxt_image})",
                         "settings": "defaults", "output": "n4.nii.gz",
                         "runtime_s": round(time.time() - t0, 1),
                         "in_mask": compare(load(r / "n4.nii.gz"), load(qo / "n4.nii.gz"), mask),
                         "where_input_gt_0": compare(load(r / "n4.nii.gz"), load(qo / "n4.nii.gz"),
                                                     head)})
    if "bestpath" in ops:
        r = need("bestpath")
        t = probe(a, "bestpath", case / "phase1.nii.gz", case / "mask3d.nii.gz", cand / "bestpath.nii.gz")
        rows.append({"op": "bestpath", "port": "qsm_core::unwrap::unwrap_bestpath (probe)",
                     "settings": "defaults", "output": "bestpath.nii.gz", "runtime_s": round(t, 1),
                     "in_mask": compare(load(r / "bestpath.nii.gz"), load(cand / "bestpath.nii.gz"), mask),
                     "wraps": wraps(load(r / "bestpath.nii.gz"), load(cand / "bestpath.nii.gz"), mask)})
    for op, ref_out, n in (("prelude", "prelude.nii.gz", "6"),
                           ("prelude-fsl-defaults", "prelude_defaults.nii.gz", "8")):
        if op not in ops:
            continue
        r = need(op)
        o = cand / f"prelude_n{n}.nii.gz"
        t = probe(a, "prelude", case / "phase1.nii.gz", case / "mask3d.nii.gz", o, "--n", n)
        rows.append({"op": op, "port": "qsm_core::unwrap::unwrap_prelude (probe)",
                     "settings": f"{n} partitions", "output": ref_out, "runtime_s": round(t, 1),
                     "in_mask": compare(load(r / ref_out), load(o), mask),
                     "wraps": wraps(load(r / ref_out), load(o), mask)})
    if "gibbs" in ops:
        r = need("gibbs")
        t = probe(a, "gibbs", case / "mag4d.nii.gz", cand / "gibbs.nii.gz")
        inp = load(case / "mag4d.nii.gz")
        rows.append({"op": "gibbs", "port": "qsm_core::unring::gibbs_unring (probe; 3-D)",
                     "settings": "defaults (DIPY: 2-D, slice_axis 2, n_points 3)",
                     "output": "gibbs.nii.gz", "runtime_s": round(t, 1),
                     "in_mask": compare(load(r / "gibbs.nii.gz"), load(cand / "gibbs.nii.gz"), mask),
                     "change_vs_input": {"original": compare(inp, load(r / "gibbs.nii.gz"), mask),
                                         "port": compare(inp, load(cand / "gibbs.nii.gz"), mask)}})
    if "mppca" in ops:
        r = need("mppca")
        t = probe(a, "mppca", case / "mag4d.nii.gz", case / "mask3d.nii.gz", cand / "mppca.nii.gz",
                  "--patch-radius", "2")
        inp = load(case / "mag4d.nii.gz")
        rows.append({"op": "mppca", "port": "qsm_core::denoise::mppca_denoise (probe)",
                     "settings": "patch radius 2, brain mask", "output": "mppca.nii.gz",
                     "runtime_s": round(t, 1),
                     "in_mask": compare(load(r / "mppca.nii.gz"), load(cand / "mppca.nii.gz"), mask),
                     "change_vs_input": {"original": compare(inp, load(r / "mppca.nii.gz"), mask),
                                         "port": compare(inp, load(cand / "mppca.nii.gz"), mask)}})
    for op, f in (("bet-f0.2", "0.2"), ("bet-f0.5", "0.5")):
        if op not in ops:
            continue
        r = need(op)
        refm = load(r / OPS[op]["outputs"][0])
        for sub in a.bet_subdivisions:
            o = cand / f"bet_f{f}_s{sub}.nii.gz"
            t = probe(a, "bet", case / "mag1_n4.nii.gz", o, "--f", f, "--subdivisions", sub)
            rows.append({"op": op, "port": "qsm_core::bet::run_bet (probe)",
                         "settings": f"f {f}, subdivisions {sub}", "output": o.name,
                         "runtime_s": round(t, 1), "mask": dice(refm, load(o))})
    md = render_pair(rows)
    write(out, "pair", rows, md)
    return 0


def _g(v, p=4):
    return f"{v:.{p}g}" if isinstance(v, float) else str(v)


def render_pair(rows: list) -> str:
    md = ["| original | port | settings | output | NRMSE % | r | max \\|Δ\\| | p99 \\|Δ\\| | "
          "max \\|Δ\\| / max \\|ref\\| | identical voxels |", "|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        if "in_mask" in r:
            m = r["in_mask"]
            md.append(f"| `{r['op']}` | {r['port']} | {r['settings']} | `{r['output']}` | "
                      f"{_g(m['nrmse'])} | {_g(m['correlation'], 6)} | {_g(m['max_abs'])} | "
                      f"{_g(m['p99_abs'])} | {_g(m['max_rel'])} | {100 * m['identical_frac']:.2f} % |")
    bet = [r for r in rows if "mask" in r]
    if bet:
        md += ["", "| original | port | settings | Dice | voxels (original / port) | voxels that differ |",
               "|---|---|---|---|---|---|"]
        md += [f"| `{r['op']}` | {r['port']} | {r['settings']} | {r['mask']['dice']:.5f} | "
               f"{r['mask']['n_ref']} / {r['mask']['n_cand']} | {r['mask']['differ']} |" for r in bet]
    for r in rows:
        if "wraps" in r:
            w = r["wraps"]
            md += ["", f"`{r['op']}` wraps (in mask, {w['voxels']} voxels): identical "
                   f"{100 * w['identical_frac']:.4f} %; same 2π offset as the most common one "
                   f"({w['global_offset_2pi']}·2π) {100 * w['same_wrap_frac']:.4f} %; largest "
                   f"difference that is not a whole number of 2π: {_g(w['max_abs_off_2pi'])} rad."]
    return "\n".join(md) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("prepare")
    p.add_argument("--case", required=True, help="dir with phase, magnitude, mask .nii.gz")
    p.add_argument("--out", required=True)
    p.set_defaults(fn=cmd_prepare)
    for name, fn in (("determinism", cmd_determinism), ("host", cmd_host), ("pair", cmd_pair)):
        p = sub.add_parser(name)
        p.add_argument("--case", required=True, help="a prepared case (harness.py prepare)")
        p.add_argument("--out", required=True)
        p.add_argument("--runner", default="podman", choices=["podman", "docker"])
        p.add_argument("--ops", default="all", help=f"comma list of {', '.join(OPS)}, or all")
        p.set_defaults(fn=fn)
        if name == "host":
            p.add_argument("--python", required=True, help="Python 3.12 with requirements.lock")
            p.add_argument("--n4-bin", required=True, help="ANTs 2.4.3 N4BiasFieldCorrection")
            p.add_argument("--bet2-bin", help="bet2 built from Bostrix/FSL-BET2 d5acd7f")
        if name == "pair":
            p.add_argument("--probe", required=True, help="qsmrs-probe binary")
            p.add_argument("--threads", type=int, default=4, help="RAYON_NUM_THREADS for QSM.rs")
            p.add_argument("--qsmxt-image", help="also run `qsmxt homogeneity --method n4` here")
            p.add_argument("--bet-subdivisions", nargs="+", default=["4", "5"])
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
