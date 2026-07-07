#!/usr/bin/env python3
"""QSM-CI pipeline runner — isolated + composed evaluation.

Discovers stage submissions under algorithms/, runs them on a dataset, scores each produced
artifact with qsm-eval, and writes results/ entries. Runs submissions directly via their run.sh
(no Docker) so it works locally; the CI workflows mirror this with containers.

Modes (see stages.yml):
  isolated  — feed each stage/span its GROUND-TRUTH consumed artifacts; score its outputs vs GT.
  composed  — chain bfr -> dipole (and spans) starting from GT totalfield; score the final chimap.
              bfr outputs are cached and reused across dipole methods (the N×M matrix).

Usage:
  python scripts/pipeline.py --dataset data/sim/dev [--mode isolated|composed|both] [--track sim]
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EVAL = ROOT / "eval" / "qsm_eval.py"

# Stage graph (mirrors stages.yml). Kept here so the runner needs no YAML dependency.
STAGES = {
    "field-mapping": {"consumes": ["phase", "magnitude", "mask", "params"], "produces": ["totalfield"]},
    "bfr": {"consumes": ["totalfield", "mask", "params"], "produces": ["localfield"]},
    "dipole": {"consumes": ["localfield", "mask", "params"], "produces": ["chimap"]},
    "unwrap+bfr": {"consumes": ["phase", "magnitude", "mask", "params"], "produces": ["localfield"]},
    "bfr+dipole": {"consumes": ["totalfield", "mask", "params"], "produces": ["chimap"]},
    "end-to-end": {"consumes": ["phase", "magnitude", "mask", "params"], "produces": ["chimap"]},
}
ARTIFACT_FILE = {
    "phase": "phase.nii.gz", "magnitude": "magnitude.nii.gz", "mask": "mask.nii.gz",
    "params": "params.json", "totalfield": "totalfield.nii.gz",
    "localfield": "localfield.nii.gz", "chimap": "chimap.nii.gz",
}
ARTIFACT_KIND = {"totalfield": "field", "localfield": "field", "chimap": "chi"}


def discover_algorithms() -> list[dict]:
    algos = []
    for d in sorted((ROOT / "algorithms").glob("*/")):
        spec = d / "algorithm.yml"
        if d.name.startswith("_") or not spec.exists():
            continue
        text = spec.read_text()
        stage = re.search(r"^stage:\s*(\S+)", text, re.M)
        image = re.search(r"^image:\s*(\S+)", text, re.M)
        if not stage:
            continue
        s = stage.group(1)
        algos.append({
            "slug": d.name, "dir": d, "stage": s, "image": image.group(1) if image else None,
            "consumes": STAGES[s]["consumes"], "produces": STAGES[s]["produces"],
        })
    return algos


def prepare_input(consumes: list[str], sources: dict[str, Path], dest: Path) -> None:
    """Populate dest with the consumed artifacts under their canonical filenames."""
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    for art in consumes:
        src = sources.get(art)
        if src is None or not Path(src).exists():
            raise SystemExit(f"missing source artifact '{art}' (looked for {src})")
        shutil.copy(src, dest / ARTIFACT_FILE[art])


def run_algo(algo: dict, input_dir: Path, output_dir: Path, runner: str = "local") -> float:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)
    t0 = time.time()
    if runner == "docker":
        import os
        # Untrusted submission: no network, read-only input, its own image (code baked in).
        # Run as the host user so /output files aren't root-owned.
        subprocess.run([
            "docker", "run", "--rm", "--network", "none",
            "--user", f"{os.getuid()}:{os.getgid()}",
            "-v", f"{input_dir}:/input:ro", "-v", f"{output_dir}:/output",
            algo["image"], "bash", "run.sh",
        ], check=True)
    else:
        subprocess.run(["bash", str(algo["dir"] / "run.sh"), str(input_dir), str(output_dir)],
                       check=True)
    return time.time() - t0


def score(recon: Path, artifact: str, gt_dir: Path, mask: Path, out_json: Path, meta: dict) -> dict:
    kind = ARTIFACT_KIND[artifact]
    cmd = [sys.executable, str(EVAL), "--recon", str(recon),
           "--truth", str(gt_dir / ARTIFACT_FILE[artifact]), "--kind", kind,
           "--mask", str(mask), "--artifact", artifact, "--out", str(out_json),
           "--stage", meta["stage"], "--name", meta["name"], "--track", meta["track"]]
    if meta.get("runtime") is not None:
        cmd += ["--runtime", str(meta["runtime"])]
    seg = gt_dir / "dseg.nii.gz"
    if kind == "chi" and seg.exists():
        cmd += ["--seg", str(seg)]
    subprocess.run(cmd, check=True)
    result = json.loads(out_json.read_text())
    result["status"] = "ok"
    result.update({k: meta[k] for k in ("id", "slug", "mode") if k in meta})
    if "combo" in meta:
        result["combo"] = meta["combo"]
    return result


def dnf(rid, slug, name, stage, mode, track, combo=None):
    e = {"contract": "v2", "name": name, "track": track, "stage": stage, "mode": mode,
         "status": "DNF", "metrics": {}, "id": rid, "slug": slug}
    if combo:
        e["combo"] = combo
    return e


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", type=Path, default=ROOT / "data/sim/dev")
    ap.add_argument("--mode", choices=["isolated", "composed", "both"], default="both")
    ap.add_argument("--runner", choices=["local", "docker"], default="local",
                    help="local runs run.sh directly; docker runs each submission's image (CI)")
    ap.add_argument("--only", default=None, help="restrict isolated evaluation to this slug")
    ap.add_argument("--track", default="sim")
    ap.add_argument("--work", type=Path, default=ROOT / ".work")
    args = ap.parse_args()

    inputs, gt = args.dataset / "inputs", args.dataset / "groundtruth"
    mask, params = inputs / "mask.nii.gz", inputs / "params.json"
    # GT-backed source map: inputs for raw artifacts, groundtruth for stage boundaries.
    gt_sources = {
        "phase": inputs / "phase.nii.gz", "magnitude": inputs / "magnitude.nii.gz",
        "mask": mask, "params": params,
        "totalfield": gt / "totalfield.nii.gz", "localfield": gt / "localfield.nii.gz",
        "chimap": gt / "chimap.nii.gz",
    }
    algos = discover_algorithms()
    print(f"discovered {len(algos)} submissions:",
          ", ".join(f"{a['slug']}[{a['stage']}]" for a in algos))
    runs: list[dict] = []
    args.work.mkdir(parents=True, exist_ok=True)

    # -------- isolated --------
    if args.mode in ("isolated", "both"):
        for a in algos:
            if args.only and a["slug"] != args.only:
                continue
            idir, odir = args.work / f"iso_{a['slug']}_in", args.work / f"iso_{a['slug']}_out"
            try:
                prepare_input(a["consumes"], gt_sources, idir)
                rt = run_algo(a, idir, odir, args.runner)
                for art in a["produces"]:
                    meta = {"id": f"{a['slug']}-iso", "slug": a["slug"], "name": a["slug"],
                            "stage": a["stage"], "mode": "isolated", "track": args.track, "runtime": rt}
                    r = score(odir / ARTIFACT_FILE[art], art, gt, mask,
                              args.work / f"iso_{a['slug']}.json", meta)
                    runs.append(r)
                    m = r["metrics"]
                    print(f"  isolated  {a['slug']:<16} {art:<11} "
                          f"xsim={m.get('xsim'):.4f} nrmse={m.get('nrmse'):.2f}%")
            except Exception as e:  # DNF — record and continue
                print(f"  isolated  {a['slug']:<16} DNF ({e})")
                runs.append(dnf(f"{a['slug']}-iso", a["slug"], a["slug"], a["stage"], "isolated", args.track))

    # -------- composed: bfr x dipole matrix (+ direct chimap spans) --------
    if args.mode in ("composed", "both"):
        bfr = [a for a in algos if "localfield" in a["produces"]]
        dipole = [a for a in algos if a["stage"] == "dipole"]
        spans = [a for a in algos if "chimap" in a["produces"] and a["stage"] != "dipole"]
        # cache each bfr's localfield output (starting from GT totalfield)
        lf_cache: dict[str, Path] = {}
        for b in bfr:
            idir, odir = args.work / f"cmp_{b['slug']}_in", args.work / f"cmp_{b['slug']}_out"
            try:
                prepare_input(b["consumes"], gt_sources, idir)
                run_algo(b, idir, odir, args.runner)
                lf_cache[b["slug"]] = odir / "localfield.nii.gz"
            except Exception as e:
                print(f"  composed  bfr {b['slug']} DNF ({e}) — skipping its combos")
        for b in bfr:
            if b["slug"] not in lf_cache:
                continue
            for d in dipole:
                combo = f"{b['slug']}+{d['slug']}"
                cinfo = {"bfr": b["slug"], "dipole": d["slug"]}
                try:
                    src = dict(gt_sources)
                    src["localfield"] = lf_cache[b["slug"]]  # chain: real bfr output -> dipole input
                    idir, odir = args.work / f"cmp_{combo}_in", args.work / f"cmp_{combo}_out"
                    prepare_input(d["consumes"], src, idir)
                    rt = run_algo(d, idir, odir, args.runner)
                    meta = {"id": f"{combo}-cmp", "slug": combo, "name": combo,
                            "stage": "bfr+dipole", "mode": "composed", "track": args.track,
                            "runtime": rt, "combo": cinfo}
                    r = score(odir / "chimap.nii.gz", "chimap", gt, mask,
                              args.work / f"cmp_{combo}.json", meta)
                    runs.append(r)
                    m = r["metrics"]
                    print(f"  composed  {combo:<28} chimap xsim={m.get('xsim'):.4f} "
                          f"nrmse_dt={m.get('nrmse_detrend'):.2f}%")
                except Exception as e:
                    print(f"  composed  {combo:<28} DNF ({e})")
                    runs.append(dnf(f"{combo}-cmp", combo, combo, "bfr+dipole", "composed", args.track, cinfo))
        for s in spans:
            idir, odir = args.work / f"cmp_{s['slug']}_in", args.work / f"cmp_{s['slug']}_out"
            try:
                prepare_input(s["consumes"], gt_sources, idir)
                rt = run_algo(s, idir, odir, args.runner)
                meta = {"id": f"{s['slug']}-cmp", "slug": s["slug"], "name": s["slug"],
                        "stage": s["stage"], "mode": "composed", "track": args.track, "runtime": rt}
                r = score(odir / "chimap.nii.gz", "chimap", gt, mask, args.work / f"cmp_{s['slug']}.json", meta)
                runs.append(r)
            except Exception as e:
                print(f"  composed  {s['slug']:<28} DNF ({e})")
                runs.append(dnf(f"{s['slug']}-cmp", s["slug"], s["slug"], s["stage"], "composed", args.track))

    # -------- merge into results/index.json (replace entries with matching id) --------
    idx = ROOT / "results" / "index.json"
    existing = json.loads(idx.read_text()).get("runs", []) if idx.exists() else []
    new_ids = {r["id"] for r in runs}
    merged = [r for r in existing if r.get("id") not in new_ids] + runs
    idx.write_text(json.dumps({"contract": "v2", "generated": None, "runs": merged}, indent=2) + "\n")
    print(f"\nmerged {len(runs)} runs into {idx} ({len(merged)} total)")


if __name__ == "__main__":
    main()
