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
import concurrent.futures as _cf
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EVAL = ROOT / "eval" / "qsm_eval.py"

# Independent submission runs (each a Docker container + a scoring subprocess) are executed
# concurrently, bounded by QSM_CI_JOBS. The cap is deliberately conservative: MATLAB MCR runs on
# the 205^3 volume peak at a few GB each, so 4 keeps well under the runner's ~31 GB. Set 1 for
# fully-serial behaviour. Threads are fine — the actual work is in subprocess.run (GIL released).
JOBS = max(1, int(os.environ.get("QSM_CI_JOBS", "4")))


def _pmap(items, fn):
    """Apply fn to each item, up to JOBS at a time, preserving input order. fn must handle its own
    errors (return a value, never raise) so one bad task can't sink the batch."""
    if JOBS <= 1 or len(items) <= 1:
        return [fn(x) for x in items]
    with _cf.ThreadPoolExecutor(max_workers=JOBS) as ex:
        return list(ex.map(fn, items))

# Stage graph (mirrors stages.yml). Kept here so the runner needs no YAML dependency.
STAGES = {
    "field-mapping": {"consumes": ["phase", "magnitude", "mask", "params"], "produces": ["totalfield"]},
    "bfr": {"consumes": ["totalfield", "mask", "params"], "produces": ["localfield"]},
    "dipole": {"consumes": ["localfield", "mask", "params", "magnitude"], "produces": ["chimap"]},
    "unwrap+bfr": {"consumes": ["phase", "magnitude", "mask", "params"], "produces": ["localfield"]},
    "bfr+dipole": {"consumes": ["totalfield", "mask", "params", "magnitude"], "produces": ["chimap"]},
    "end-to-end": {"consumes": ["phase", "magnitude", "mask", "params"], "produces": ["chimap"]},
}
ARTIFACT_FILE = {
    "phase": "phase.nii.gz", "magnitude": "magnitude.nii.gz", "mask": "mask.nii.gz",
    "params": "params.json", "totalfield": "totalfield.nii.gz",
    "localfield": "localfield.nii.gz", "chimap": "chimap.nii.gz",
}
ARTIFACT_KIND = {"totalfield": "field", "localfield": "field", "chimap": "chi"}

EMIT_VOLUMES = False  # when set, write recon/truth/error NIfTIs per run for the web viewer


def emit_volumes(run_id, recon, truth):
    """Write recon / truth / error volumes under results/<run_id>/ for the NiiVue viewer."""
    import nibabel as nib
    d = ROOT / "results" / run_id
    d.mkdir(parents=True, exist_ok=True)
    shutil.copy(recon, d / "recon.nii.gz")
    shutil.copy(truth, d / "truth.nii.gz")
    r, t = nib.load(str(recon)), nib.load(str(truth))
    err = nib.Nifti1Image((r.get_fdata() - t.get_fdata()).astype("float32"), r.affine)
    nib.save(err, str(d / "error.nii.gz"))


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


_built: dict[str, str] = {}


def build_env(algo: dict) -> str:
    """Resolve the submission's ENVIRONMENT image (build/setup phase — network allowed).

    - If the folder has a Dockerfile, build it (a base image + any toolbox downloads). The code is
      NOT baked in; it is mounted at run time.
    - Otherwise use `image:` (a ready base, e.g. a MATLAB Runtime container), pulling if not local.
    Returns the image tag to run offline.
    """
    if algo["slug"] in _built:
        return _built[algo["slug"]]
    if (algo["dir"] / "Dockerfile").exists():
        tag = f"qsm-ci-env/{algo['slug']}:latest"
        subprocess.run(["docker", "build", "-q", "-t", tag, str(algo["dir"])], check=True)
    else:
        tag = algo["image"]
        # Always pull: submissions push updated builds to the SAME tag (e.g. matlab-*:v1), so a
        # stale copy cached from a prior run would otherwise be used silently (docker image inspect
        # succeeds and skips the pull). `docker pull` is cheap when the digest already matches.
        if subprocess.run(["docker", "pull", tag], capture_output=True).returncode != 0:
            # Offline / registry hiccup — fall back to a locally cached image if one exists.
            if subprocess.run(["docker", "image", "inspect", tag], capture_output=True).returncode != 0:
                raise RuntimeError(f"cannot pull or find image {tag}")
    _built[algo["slug"]] = tag
    return tag


def run_algo(algo: dict, input_dir: Path, output_dir: Path, runner: str = "local") -> float:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)
    t0 = time.time()
    if runner == "docker":
        import os
        # Run phase: no network, read-only input, the submission's CODE mounted at /algo (not baked).
        subprocess.run([
            "docker", "run", "--rm", "--network", "none",
            "--user", f"{os.getuid()}:{os.getgid()}",
            "-v", f"{algo['dir']}:/algo:ro",
            "-v", f"{input_dir}:/input:ro", "-v", f"{output_dir}:/output",
            algo["image"], "bash", "/algo/run.sh",
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
    if EMIT_VOLUMES and "id" in meta:
        emit_volumes(meta["id"], recon, gt_dir / ARTIFACT_FILE[artifact])
    return result


def dnf(rid, slug, name, stage, mode, track, combo=None):
    e = {"name": name, "track": track, "stage": stage, "mode": mode,
         "status": "DNF", "metrics": {}, "id": rid, "slug": slug}
    if combo:
        e["combo"] = combo
    return e


def flush_index(runs):
    """Merge the current runs into results/index.json (replace matching ids) and write immediately,
    so a long run's progress is visible on the leaderboard as it goes."""
    idx = ROOT / "results" / "index.json"
    idx.parent.mkdir(parents=True, exist_ok=True)
    existing = json.loads(idx.read_text()).get("runs", []) if idx.exists() else []
    ids = {r["id"] for r in runs}
    merged = [r for r in existing if r.get("id") not in ids] + runs
    idx.write_text(json.dumps({"generated": None, "runs": merged}, indent=2) + "\n")
    return len(merged)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", type=Path, default=ROOT / "data/sim/dev")
    ap.add_argument("--mode", choices=["isolated", "composed", "both"], default="both")
    ap.add_argument("--runner", choices=["local", "docker"], default="local",
                    help="local runs run.sh directly; docker runs each submission's image (CI)")
    ap.add_argument("--only", default=None, help="restrict isolated evaluation to this slug")
    ap.add_argument("--focus", default=None,
                    help="incremental: isolated for this slug, and every composed combo that includes "
                         "it (its own stage is pinned to it; complementary stages stay full)")
    ap.add_argument("--include", default=None, help="comma-separated slugs to restrict the run to")
    ap.add_argument("--track", default="sim")
    ap.add_argument("--work", type=Path, default=ROOT / ".work")
    ap.add_argument("--emit-volumes", action="store_true",
                    help="write recon/truth/error NIfTIs per run under results/<id>/ for the web viewer")
    args = ap.parse_args()

    global EMIT_VOLUMES
    EMIT_VOLUMES = args.emit_volumes

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
    if args.include:
        keep = set(args.include.split(","))
        algos = [a for a in algos if a["slug"] in keep]
    print(f"discovered {len(algos)} submissions:",
          ", ".join(f"{a['slug']}[{a['stage']}]" for a in algos))
    runs: list[dict] = []
    args.work.mkdir(parents=True, exist_ok=True)

    # Build/setup phase (network allowed): resolve each submission's environment image. Code is
    # mounted at run time, not baked. A submission whose env can't be built is excluded (DNF).
    if args.runner == "docker":
        ok = []
        iso_only = args.focus or args.only  # in pure isolated mode, only this slug needs building
        for a in algos:
            if iso_only and a["slug"] != iso_only and args.mode == "isolated":
                ok.append(a)
                continue
            try:
                a["image"] = build_env(a)
                ok.append(a)
            except Exception as e:
                print(f"  build     {a['slug']:<16} env FAILED ({e}) — excluded")
                runs.append(dnf(f"{a['slug']}-iso", a["slug"], a["slug"], a["stage"], "isolated", args.track))
        algos = ok

    iso_target = args.focus or args.only  # isolated runs only this slug when set

    # -------- isolated (independent runs -> parallel) --------
    if args.mode in ("isolated", "both"):
        iso_algos = [a for a in algos if not (iso_target and a["slug"] != iso_target)]

        def do_isolated(a):
            idir, odir = args.work / f"iso_{a['slug']}_in", args.work / f"iso_{a['slug']}_out"
            try:
                prepare_input(a["consumes"], gt_sources, idir)
                rt = run_algo(a, idir, odir, args.runner)
                out = []
                for art in a["produces"]:
                    meta = {"id": f"{a['slug']}-iso", "slug": a["slug"], "name": a["slug"],
                            "stage": a["stage"], "mode": "isolated", "track": args.track, "runtime": rt}
                    r = score(odir / ARTIFACT_FILE[art], art, gt, mask,
                              args.work / f"iso_{a['slug']}.json", meta)
                    out.append(r)
                    m = r["metrics"]
                    print(f"  isolated  {a['slug']:<16} {art:<11} "
                          f"xsim={m.get('xsim'):.4f} nrmse={m.get('nrmse'):.2f}%")
                return out
            except Exception as e:  # DNF — record and continue
                print(f"  isolated  {a['slug']:<16} DNF ({e})")
                return [dnf(f"{a['slug']}-iso", a["slug"], a["slug"], a["stage"], "isolated", args.track)]

        for out in _pmap(iso_algos, do_isolated):
            runs.extend(out)
        flush_index(runs)

    # -------- composed: (field-mapping) x bfr x dipole, chaining real outputs --------
    # Dependency order is fieldmap -> bfr -> dipole, so each stage is a barrier; but every
    # combo within a stage is independent, so each stage fans out over the pool.
    if args.mode in ("composed", "both"):
        fmap = [a for a in algos if "totalfield" in a["produces"]]
        bfr = [a for a in algos if "localfield" in a["produces"]]
        dipole = [a for a in algos if a["stage"] == "dipole"]
        spans = [a for a in algos if "chimap" in a["produces"] and a["stage"] != "dipole"]

        if args.focus:  # pin the focus's own stage to it; every combo that includes it still runs
            f = next((a for a in algos if a["slug"] == args.focus), None)
            if f is None:
                fmap, bfr, dipole, spans = [], [], [], []
            elif f["stage"] == "dipole":
                dipole, spans = [f], []
            elif "localfield" in f["produces"]:      # a bfr (or unwrap+bfr) — this bfr × all dipoles
                bfr, spans = [f], []
            elif "totalfield" in f["produces"]:      # a field-mapping — this map through the matrix
                fmap, spans = [f], []
            else:                                     # a bfr+dipole / end-to-end span — run it alone
                fmap, bfr, dipole, spans = [], [], [], [f]

        # Stage 1 — totalfield sources: the ground-truth field ("gt") plus each field-mapping
        # submission's output (run on raw inputs), so the matrix can start from raw phase.
        tf_sources: dict[str, Path] = {"gt": gt / ARTIFACT_FILE["totalfield"]}

        def do_fieldmap(f):
            idir, odir = args.work / f"cmp_fm_{f['slug']}_in", args.work / f"cmp_fm_{f['slug']}_out"
            try:
                prepare_input(f["consumes"], gt_sources, idir)
                run_algo(f, idir, odir, args.runner)
                return (f["slug"], odir / "totalfield.nii.gz")
            except Exception as e:
                print(f"  composed  fieldmap {f['slug']} DNF ({e}) — skipping its pipelines")
                return None

        for res in _pmap(fmap, do_fieldmap):
            if res:
                tf_sources[res[0]] = res[1]

        # Stage 2 — bfr: localfield for each (totalfield source, bfr), keyed (tfk, bfr slug).
        lf_cache: dict[tuple, Path] = {}

        def do_bfr(task):
            tfk, tfp, b = task
            idir, odir = args.work / f"cmp_{tfk}_{b['slug']}_in", args.work / f"cmp_{tfk}_{b['slug']}_out"
            try:
                src = dict(gt_sources); src["totalfield"] = tfp
                prepare_input(b["consumes"], src, idir)
                run_algo(b, idir, odir, args.runner)
                return ((tfk, b["slug"]), odir / "localfield.nii.gz")
            except Exception as e:
                print(f"  composed  {tfk}+{b['slug']} bfr DNF ({e})")
                return None

        bfr_tasks = [(tfk, tfp, b) for tfk, tfp in tf_sources.items() for b in bfr]
        for res in _pmap(bfr_tasks, do_bfr):
            if res:
                lf_cache[res[0]] = res[1]

        # Stage 3 — dipole: invert each cached localfield with every dipole method.
        def do_dipole(task):
            tfk, b, d = task
            combo = f"{b['slug']}+{d['slug']}" if tfk == "gt" else f"{tfk}+{b['slug']}+{d['slug']}"
            cid = f"{tfk}~{b['slug']}~{d['slug']}-cmp"
            cinfo = {"field_mapping": tfk, "bfr": b["slug"], "dipole": d["slug"]}
            try:
                src = dict(gt_sources); src["localfield"] = lf_cache[(tfk, b["slug"])]
                idir, odir = args.work / f"cmp_{cid}_in", args.work / f"cmp_{cid}_out"
                prepare_input(d["consumes"], src, idir)
                rt = run_algo(d, idir, odir, args.runner)
                meta = {"id": cid, "slug": combo, "name": combo,
                        "stage": "bfr+dipole" if tfk == "gt" else "field-mapping+bfr+dipole",
                        "mode": "composed", "track": args.track, "runtime": rt, "combo": cinfo}
                r = score(odir / "chimap.nii.gz", "chimap", gt, mask,
                          args.work / f"cmp_{cid}.json", meta)
                m = r["metrics"]
                print(f"  composed  {combo:<34} chimap xsim={m.get('xsim'):.4f} "
                      f"nrmse_dt={m.get('nrmse_detrend'):.2f}%")
                return r
            except Exception as e:
                print(f"  composed  {combo:<34} DNF ({e})")
                return dnf(cid, combo, combo, "field-mapping+bfr+dipole", "composed", args.track, cinfo)

        dip_tasks = [(tfk, b, d) for tfk in tf_sources for b in bfr
                     if (tfk, b["slug"]) in lf_cache for d in dipole]
        for r in _pmap(dip_tasks, do_dipole):
            runs.append(r)
        flush_index(runs)

        # Stage 4 — spans (bfr+dipole / end-to-end submissions), independent.
        def do_span(s):
            idir, odir = args.work / f"cmp_{s['slug']}_in", args.work / f"cmp_{s['slug']}_out"
            try:
                prepare_input(s["consumes"], gt_sources, idir)
                rt = run_algo(s, idir, odir, args.runner)
                meta = {"id": f"{s['slug']}-cmp", "slug": s["slug"], "name": s["slug"],
                        "stage": s["stage"], "mode": "composed", "track": args.track, "runtime": rt}
                return score(odir / "chimap.nii.gz", "chimap", gt, mask,
                             args.work / f"cmp_{s['slug']}.json", meta)
            except Exception as e:
                print(f"  composed  {s['slug']:<28} DNF ({e})")
                return dnf(f"{s['slug']}-cmp", s["slug"], s["slug"], s["stage"], "composed", args.track)

        for r in _pmap(spans, do_span):
            runs.append(r)

    total = flush_index(runs)
    print(f"\nmerged {len(runs)} runs into results/index.json ({total} total)")


if __name__ == "__main__":
    main()
