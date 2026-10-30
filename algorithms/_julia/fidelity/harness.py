#!/usr/bin/env python3
"""Fidelity and first-look pair checks for the Julia-original submissions (QSMxT/QSM-CI#299).

A Julia submission is the authors' package in its own pinned environment, so its fidelity check
asks three things, all answered by running the submission exactly as QSM-CI does (`qsm-ci run`):

  determinism  the image twice on the same inputs gives bit-identical output, at the fixed thread
               count run.sh sets; with --local, run.sh outside the container (a host Julia 1.10.11
               with the same Manifest, no sysimage) gives the same output too.
  pair         a first look at the original against its QSM.rs port (`<algorithm>-qsmrs`) on the
               same inputs: NRMSE, correlation and max |Δ| inside the mask, with the original at
               its defaults and at the QSM.rs-matched settings (the README's table).

A case is a directory holding the artifacts a stage reads (phase/magnitude/mask/params.json and
totalfield/localfield, any subset); each method runs on the cases that have its inputs.

  python algorithms/_julia/fidelity/harness.py determinism --case sim=data/sim/case \\
      --runner podman [--local /path/to/julia-1.10.11/bin --local-project ... --local-depot ...]
  python algorithms/_julia/fidelity/harness.py pair --case invivo=data/th/case --runner podman

Writes <out>/<mode>.json and <out>/<mode>.md (default out: fidelity-out/).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import nibabel as nib
import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[3]
ALGOS = ROOT / "algorithms"
FILES = {"phase": "phase.nii.gz", "magnitude": "magnitude.nii.gz", "mask": "mask.nii.gz",
         "params": "params.json", "totalfield": "totalfield.nii.gz",
         "localfield": "localfield.nii.gz"}
OUTPUT = {"field-mapping": "totalfield", "bfr": "localfield", "dipole": "chimap",
          "bfr+dipole": "chimap"}


def julia_slugs() -> list[str]:
    return sorted(p.parent.name for p in ALGOS.glob("*/qsmci_io.jl") if p.parent.name != "_julia")


def manifest(slug: str) -> dict:
    m = yaml.safe_load((ALGOS / slug / "algorithm.yml").read_text())
    if not m.get("inputs"):      # no subset declared: everything the stage consumes
        reg = yaml.safe_load((ROOT / "stages.yml").read_text())
        m["inputs"] = {**reg["stages"], **reg["spans"]}[m["stage"]]["consumes"]
    return m


def matched_settings(slug: str) -> list[str]:
    """`NAME=VALUE` pairs from the README's QSM.rs-matched column (first token of each cell)."""
    out = []
    for line in (ALGOS / slug / "README.md").read_text().splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 4 and cells[0].startswith("`") and cells[2]:
            name, v = cells[0].strip("`"), cells[2].split(" ")[0]
            if name not in ("alpha0", "alpha1"):        # TGV's α depend on TE/B0: tgv_alpha()
                out.append(f"{name}={v}")
    return out


def run(slug: str, case: Path, out: Path, runner: str, sets: list[str], env: dict | None = None,
        params: Path | None = None) -> float:
    m = manifest(slug)
    inputs = m["inputs"]
    args = [sys.executable, "-m", "qsm_ci.cli", "run", slug, "--runner", runner, "-o", str(out)]
    for art in inputs:
        f = (params if art == "params" and params else case / FILES[art])
        args += [f"--{art}", str(f)]
    if "mask" not in inputs:
        args += ["--mask", str(case / FILES["mask"])]
    for s in sets:
        args += ["--set", s]
    out.parent.mkdir(parents=True, exist_ok=True)
    t = time.monotonic()
    subprocess.run(args, cwd=ROOT, check=True, env={**os.environ, **(env or {})})
    return time.monotonic() - t


def has_inputs(slug: str, case: Path) -> bool:
    return all((case / FILES[a]).exists() for a in manifest(slug)["inputs"])


def load(p: Path):
    img = nib.load(str(p))
    return np.asarray(img.dataobj, dtype=np.float64), img.affine


def sha(p: Path) -> str:
    img = nib.load(str(p))
    return hashlib.sha256(np.ascontiguousarray(np.asarray(img.dataobj)).tobytes()).hexdigest()[:16]


def compare(a: Path, b: Path, mask: np.ndarray | None = None) -> dict:
    x, ax = load(a)
    y, ay = load(b)
    d = {"identical": bool(np.array_equal(x, y) and np.allclose(ax, ay)),
         "max_abs_diff": float(np.max(np.abs(x - y))), "sha_a": sha(a), "sha_b": sha(b)}
    if mask is not None:
        sel = mask & (x != 0) & (y != 0)        # both defined (bfr/TGV erode the mask)
        xs, ys = x[sel], y[sel]
        d.update(voxels=int(sel.sum()),
                 nrmse_pct=float(100 * np.linalg.norm(xs - ys) / np.linalg.norm(ys)),
                 correlation=float(np.corrcoef(xs, ys)[0, 1]),
                 max_abs_diff_in_mask=float(np.max(np.abs(xs - ys))))
    return d


def cases(items: list[str]) -> dict[str, Path]:
    return {k: Path(v).resolve() for k, v in (i.split("=", 1) for i in items)}


def cmd_determinism(a) -> list[dict]:
    rows = []
    env_local = None
    if a.local:
        env_local = {"PATH": f"{a.local}:{os.environ['PATH']}", "JULIA_PROJECT": a.local_project,
                     "JULIA_DEPOT_PATH": a.local_depot, "QSMCI_JULIA_SYSIMAGE": ""}
    for slug in a.slugs or julia_slugs():
        for name, case in cases(a.case).items():
            if not has_inputs(slug, case):
                continue
            o = Path(a.out) / "determinism" / slug / name
            f = OUTPUT[manifest(slug)["stage"]] + ".nii.gz"
            t1 = run(slug, case, o / "image-1" / f, a.runner, [])
            t2 = run(slug, case, o / "image-2" / f, a.runner, [])
            row = {"slug": slug, "case": name, "seconds": [round(t1, 1), round(t2, 1)],
                   "image_twice": compare(o / "image-1" / f, o / "image-2" / f)}
            if env_local:
                t3 = run(slug, case, o / "host" / f, "local", [], env_local)
                row["seconds"].append(round(t3, 1))
                row["image_vs_host"] = compare(o / "image-1" / f, o / "host" / f)
            rows.append(row)
            print(json.dumps(row), flush=True)
    return rows


def cmd_pair(a) -> list[dict]:
    rows = []
    for slug in a.slugs or julia_slugs():
        m = manifest(slug)
        port = f"{m['algorithm']}-qsmrs"
        for name, case in cases(a.case).items():
            if not (has_inputs(slug, case) and has_inputs(port, case)):
                continue
            mask = load(case / FILES["mask"])[0] > 0.5
            o = Path(a.out) / "pair" / slug / name
            f = OUTPUT[m["stage"]] + ".nii.gz"
            tq = run(port, case, o / "qsmrs" / f, a.runner, [])
            row = {"slug": slug, "port": port, "case": name, "seconds": {"qsmrs": round(tq, 1)}}
            for label, sets in (("default", []), ("matched", matched_settings(slug))):
                if label == "matched" and not sets:
                    row["matched"] = dict(row["default"], settings=[])
                    continue
                if label == "matched" and m["algorithm"] == "tgv":
                    sets = sets + tgv_alpha(case)
                t = run(slug, case, o / label / f, a.runner, sets)
                row["seconds"][label] = round(t, 1)
                row[label] = dict(compare(o / label / f, o / "qsmrs" / f, mask), settings=sets)
            rows.append(row)
            print(json.dumps(row), flush=True)
    return rows


def tgv_alpha(case: Path) -> list[str]:
    """QSM.rs's ppm α defaults (v0.39.0) in the package's rad units at the case's first TE."""
    p = json.loads((case / FILES["params"]).read_text())
    te = p["TE"][0] if isinstance(p["TE"], list) else p["TE"]
    c = 2 * np.pi * 42.5781 * p["B0"] * te
    ref = 2 * np.pi * 42.5781 * 7 * 0.004                 # QSM.rs's α reference point, 7 T / 4 ms
    return [f"alpha1={0.0005 / ref * c:.6g}", f"alpha0={0.0015 / ref * c:.6g}"]


def markdown(mode: str, rows: list[dict]) -> str:
    if mode == "determinism":
        lines = ["| method | case | image twice | image vs host | max abs diff | run time, s |",
                 "|---|---|---|---|---|---|"]
        for r in rows:
            h = r.get("image_vs_host")
            lines.append(f"| `{r['slug']}` | {r['case']} | {'identical' if r['image_twice']['identical'] else 'DIFFERENT'} "
                         f"| {'' if h is None else ('identical' if h['identical'] else 'DIFFERENT')} "
                         f"| {max(r['image_twice']['max_abs_diff'], (h or {}).get('max_abs_diff', 0)):.3g} "
                         f"| {' / '.join(str(s) for s in r['seconds'])} |")
        return "\n".join(lines) + "\n"
    lines = ["| method | case | settings | NRMSE vs port, % | correlation | max abs diff in mask |",
             "|---|---|---|---|---|---|"]
    for r in rows:
        for label in ("default", "matched"):
            d = r[label]
            lines.append(f"| `{r['slug']}` | {r['case']} | {label} | {d['nrmse_pct']:.3g} | "
                         f"{d['correlation']:.6f} | {d['max_abs_diff_in_mask']:.3g} |")
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=["determinism", "pair"])
    ap.add_argument("--case", action="append", required=True, help="NAME=DIR (repeatable)")
    ap.add_argument("--slugs", nargs="*", help="default: every Julia submission")
    ap.add_argument("--runner", default="docker", choices=["docker", "podman", "apptainer"])
    ap.add_argument("--local", help="determinism: directory holding a host `julia` (1.10.11)")
    ap.add_argument("--local-project", help="determinism: project with the same Manifest")
    ap.add_argument("--local-depot", help="determinism: depot that project is instantiated in")
    ap.add_argument("--out", default="fidelity-out")
    a = ap.parse_args()
    rows = cmd_determinism(a) if a.mode == "determinism" else cmd_pair(a)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{a.mode}.json").write_text(json.dumps(rows, indent=2) + "\n")
    (out / f"{a.mode}.md").write_text(markdown(a.mode, rows))
    print(markdown(a.mode, rows))
    if a.mode == "determinism":
        bad = [r for r in rows if not r["image_twice"]["identical"]
               or not r.get("image_vs_host", {"identical": True})["identical"]]
        sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
