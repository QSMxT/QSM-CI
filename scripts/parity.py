#!/usr/bin/env python3
"""Port parity: run two implementations of one algorithm on the same dataset and check they agree.

A *pair* is two submissions with the same `algorithm:` in algorithm.yml, one of them the QSM.rs port
(`source: qsmrs`) and the other the original (any other source) — e.g. qsmart-matlab vs qsmart-qsmrs.
`parity/thresholds.yml` names which pairs are checked, which side is the reference, and the limits
each comparison must stay inside on each dataset (see the comments there).

Subcommands (the `parity` workflow runs them in this order):

  pairs    list the pairs algorithm.yml defines and whether each is enabled, as JSON (`--matrix`
           prints the workflow's job matrix for an algorithm/dataset selection instead).
  run      run the reference and then the candidate on one dataset through `qsm-ci run` (the same
           run path score.yml uses), collecting each side's produced artifact and its intermediates.
  compare  compare the two sides inside the dataset mask — the final artifact and every
           intermediate both sides wrote under the same name — against the thresholds, write a
           markdown report and a JSON result, and exit 1 if any limit is exceeded.

Intermediates join by NAME: a method that is run with `qsm-ci run --intermediates DIR` writes
`$QSMCI_INTERMEDIATES/<name>.nii.gz` (CONTRACT.md, "Intermediates"), and an intermediate is compared
only when both sides wrote one with that name. Binary maps (values in {0, 1} on both sides) are
compared by Dice; everything else by NRMSE, correlation and |Δ|.

`compare --baseline` measures without failing and prints limits derived from what it measured
(`derive_limits`) for pasting into parity/thresholds.yml.

Usage:
  python scripts/parity.py pairs
  python scripts/parity.py run --algorithm qsmart --dataset data/sim/scoring --work .parity
  python scripts/parity.py compare --algorithm qsmart --phantom sim --dataset data/sim/scoring \\
      --work .parity --report parity-report.md --json parity.json
"""

from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
THRESHOLDS = ROOT / "parity" / "thresholds.yml"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Metric names, the direction a limit applies in, and how they print. A limit in thresholds.yml is
# `<metric>_max` or `<metric>_min`; `compare` checks every limit given and ignores metrics without one.
CONTINUOUS = ("nrmse", "correlation", "max_abs", "p99_abs")
BINARY = ("dice",)
UNITS = {"nrmse": "%", "max_abs": " ppm", "p99_abs": " ppm"}

# Baseline margins (derive_limits). The two containers are pinned by digest, so a rerun on the same
# data reproduces today's numbers up to thread-order noise; the margin is there for that noise and
# for small, deliberate changes on either side, not to absorb a real regression.
NRMSE_REL, NRMSE_ABS = 0.10, 0.5        # +10 % of the measured NRMSE, +0.5 percentage points
CORR_ABS = 0.01                         # correlation may drop by 0.01
ABS_REL = 0.25                          # max |Δ| and p99 |Δ| may grow by 25 %
DICE_ABS = 0.01                         # Dice may drop by 0.01


# ---------------------------------------------------------------------------------------------------
# Pairs
# ---------------------------------------------------------------------------------------------------

def load_thresholds(path: Path = THRESHOLDS) -> dict:
    doc = yaml.safe_load(Path(path).read_text()) or {}
    return doc.get("pairs") or {}


def discover_pairs(algorithms_dir: Path = ROOT / "algorithms") -> dict:
    """{algorithm: {"original": [slugs], "port": [slugs]}} for every `algorithm:` that has both a
    QSM.rs port (`source: qsmrs`) and at least one other implementation. Skipped (`ci_skip`) methods
    are kept: whether a pair runs is thresholds.yml's call, and the listing should show it exists."""
    groups: dict = {}
    for spec in sorted(Path(algorithms_dir).glob("*/algorithm.yml")):
        if spec.parent.name.startswith("_"):
            continue
        try:
            doc = yaml.safe_load(spec.read_text()) or {}
        except yaml.YAMLError:
            continue
        alg = doc.get("algorithm")
        if not alg:
            continue
        side = "port" if str(doc.get("source", "")) == "qsmrs" else "original"
        groups.setdefault(str(alg), {"original": [], "port": []})[side].append(spec.parent.name)
    return {a: g for a, g in groups.items() if g["original"] and g["port"]}


def pair_listing(pairs: dict, thresholds: dict) -> list:
    rows = []
    for alg in sorted(set(pairs) | set(thresholds)):
        cfg = thresholds.get(alg) or {}
        found = pairs.get(alg, {"original": [], "port": []})
        rows.append({
            "algorithm": alg,
            "reference": cfg.get("reference") or (found["original"][:1] or [None])[0],
            "candidate": cfg.get("candidate") or (found["port"][:1] or [None])[0],
            "enabled": bool(cfg.get("enabled")),
            "datasets": sorted((cfg.get("datasets") or {}).keys()),
            "defined": alg in pairs,
        })
    return rows


def plan_matrix(thresholds: dict, algorithm: str, dataset: str) -> list:
    """The workflow's job matrix: one {algorithm, phantom} per selected pair × dataset.

    `algorithm` is a pair name or `enabled` (every enabled pair). `dataset` is a dataset key or
    `configured` (every dataset that pair has a thresholds entry for). Naming a disabled pair
    explicitly still runs it — that is how a new pair gets its first baseline."""
    if algorithm == "enabled":
        algs = [a for a, c in thresholds.items() if (c or {}).get("enabled")]
    else:
        if algorithm not in thresholds:
            raise SystemExit(f"no pair '{algorithm}' in parity/thresholds.yml "
                             f"(known: {', '.join(sorted(thresholds))})")
        algs = [algorithm]
    out = []
    for a in algs:
        cfg = thresholds[a] or {}
        dss = sorted((cfg.get("datasets") or {}).keys()) if dataset == "configured" else [dataset]
        if not dss:
            dss = ["sim"]
        out += [{"algorithm": a, "phantom": d} for d in dss]
    return out


def pair_config(thresholds: dict, algorithm: str) -> dict:
    cfg = thresholds.get(algorithm)
    if not cfg or not cfg.get("reference") or not cfg.get("candidate"):
        raise SystemExit(f"parity/thresholds.yml: pair '{algorithm}' needs reference: and candidate:")
    return cfg


def side_chain(cfg: dict, side: str, phantom: str) -> list:
    """The slugs one side runs, in order. Normally just the reference/candidate slug; a dataset entry
    may prefix it (`<side>_prefix: [laplacian-qsmrs]`) when the dataset lacks the stage boundary that
    side consumes — e.g. an in-vivo acquisition with no ground-truth total field."""
    ds = (cfg.get("datasets") or {}).get(phantom) or {}
    return list(ds.get(f"{side}_prefix") or []) + [cfg[side]]


# ---------------------------------------------------------------------------------------------------
# Comparison (pure numpy — unit-tested in tests/test_parity.py)
# ---------------------------------------------------------------------------------------------------

def is_binary(a) -> bool:
    import numpy as np
    a = np.asarray(a)
    return a.size > 0 and bool(np.isin(a, (0, 1)).all())


def compare_maps(ref, cand, mask) -> dict:
    """Agreement of `cand` with `ref` inside `mask` (all the same shape).

    Binary on both sides → {"kind": "binary", "dice", "n_ref", "n_cand"}. Otherwise continuous:
    nrmse = 100·‖cand − ref‖ / ‖ref‖ (%), Pearson correlation, max and 99th-percentile |cand − ref|,
    and `nonfinite`, the voxels where either side is NaN/inf (left out of the metrics; any such voxel
    fails the comparison in `check`)."""
    import numpy as np
    ref, cand, mask = np.asarray(ref, float), np.asarray(cand, float), np.asarray(mask) > 0.5
    if ref.shape != cand.shape or ref.shape != mask.shape:
        raise ValueError(f"shape mismatch: reference {ref.shape}, candidate {cand.shape}, "
                         f"mask {mask.shape}")
    r, c = ref[mask], cand[mask]
    if is_binary(r) and is_binary(c):
        rb, cb = r > 0.5, c > 0.5
        denom = rb.sum() + cb.sum()
        dice = 1.0 if denom == 0 else float(2 * (rb & cb).sum() / denom)
        return {"kind": "binary", "dice": dice, "n_ref": int(rb.sum()), "n_cand": int(cb.sum()),
                "voxels": int(mask.sum())}
    fin = np.isfinite(r) & np.isfinite(c)
    r, c = r[fin], c[fin]
    d = c - r
    nr = float(np.linalg.norm(r))
    nrmse = (0.0 if not d.any() else math.inf) if nr == 0 else float(100 * np.linalg.norm(d) / nr)
    if r.size > 1 and r.std() > 0 and c.std() > 0:
        corr = float(np.corrcoef(r, c)[0, 1])
    else:
        corr = 1.0 if r.size and np.array_equal(r, c) else float("nan")
    ad = np.abs(d)
    return {"kind": "continuous", "nrmse": nrmse, "correlation": corr,
            "max_abs": float(ad.max()) if ad.size else 0.0,
            "p99_abs": float(np.percentile(ad, 99)) if ad.size else 0.0,
            "nonfinite": int((~fin).sum()), "voxels": int(mask.sum())}


def check(metrics: dict, limits: "dict | None") -> list:
    """One row per limit: {metric, value, op, limit, ok}. A `<m>_max` limit passes when value ≤ limit,
    `<m>_min` when value ≥ limit; a missing or non-finite value fails. Non-finite voxels in a
    continuous comparison add a failing `nonfinite` row whatever the limits say."""
    rows = []
    for key, lim in sorted((limits or {}).items()):
        if key.endswith("_max"):
            m, op = key[:-4], "<="
        elif key.endswith("_min"):
            m, op = key[:-4], ">="
        else:
            raise ValueError(f"unknown limit '{key}' (expected <metric>_max or <metric>_min)")
        v = metrics.get(m)
        good = isinstance(v, (int, float)) and math.isfinite(v)
        ok = good and (v <= lim if op == "<=" else v >= lim)
        rows.append({"metric": m, "value": v, "op": op, "limit": lim, "ok": bool(ok)})
    if metrics.get("nonfinite"):
        rows.append({"metric": "nonfinite", "value": metrics["nonfinite"], "op": "==", "limit": 0,
                     "ok": False})
    return rows


def _round_up(x: float, sig: int = 3) -> float:
    if x <= 0 or not math.isfinite(x):
        return x
    e = math.floor(math.log10(x)) - sig + 1
    return round(math.ceil(x / 10 ** e) * 10 ** e, max(0, -e))   # round(): no 2.7600000000000002


def _round_down(x: float, nd: int = 3) -> float:
    return round(math.floor(x * 10 ** nd) / 10 ** nd, nd)


def derive_limits(metrics: dict) -> dict:
    """Limits for a baseline: today's measured agreement plus the margins above, rounded outward."""
    if metrics.get("kind") == "binary":
        return {"dice_min": max(0.0, _round_down(metrics["dice"] - DICE_ABS))}
    out = {"nrmse_max": _round_up(metrics["nrmse"] * (1 + NRMSE_REL) + NRMSE_ABS)}
    if math.isfinite(metrics.get("correlation", float("nan"))):
        out["correlation_min"] = max(-1.0, _round_down(metrics["correlation"] - CORR_ABS))
    out["max_abs_max"] = _round_up(metrics["max_abs"] * (1 + ABS_REL))
    out["p99_abs_max"] = _round_up(metrics["p99_abs"] * (1 + ABS_REL))
    return out


def evaluate(results: dict, ds_cfg: dict, final: str) -> dict:
    """Apply the dataset's limits to every compared map. `results` is {name: metrics} with the final
    artifact under its artifact name (e.g. "chimap") and intermediates under theirs. The final
    artifact's limits are ds_cfg[final]; an intermediate's are ds_cfg["intermediates"][name].

    Returns {name: {"metrics", "checks", "status"}} with status "pass", "fail" or "info" (compared
    but no limits configured — reported, never fails), plus "ok": no "fail" anywhere and the final
    artifact has limits. A final artifact without limits is "fail": an enabled pair must say what
    agreement it expects."""
    inter = (ds_cfg or {}).get("intermediates") or {}
    out = {}
    for name, metrics in results.items():
        limits = (ds_cfg or {}).get(name) if name == final else inter.get(name)
        rows = check(metrics, limits)
        if not limits and name == final:
            status = "fail"
        elif not limits:
            status = "fail" if any(not r["ok"] for r in rows) else "info"
        else:
            status = "pass" if all(r["ok"] for r in rows) else "fail"
        out[name] = {"metrics": metrics, "checks": rows, "status": status,
                     "limits": limits or {}}
    return {"maps": out, "ok": bool(out) and all(v["status"] != "fail" for v in out.values())}


# ---------------------------------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------------------------------

def _fmt(v, metric: str = "") -> str:
    if not isinstance(v, (int, float)) or isinstance(v, bool):
        return "—" if v is None else str(v)
    if not math.isfinite(v):
        return str(v)
    if metric in ("n_ref", "n_cand", "voxels", "nonfinite"):
        return f"{int(v):,}"
    s = f"{v:.4g}" if abs(v) < 1e4 else f"{v:,.0f}"
    return s + UNITS.get(metric, "")


def render_report(*, algorithm: str, phantom: str, reference: str, candidate: str, verdict: dict,
                  baseline: bool, unmatched: dict, provenance: dict) -> str:
    maps = verdict["maps"]
    if baseline:
        head = "📏 **Baseline measured** (no limits applied)"
    else:
        head = "✅ **Parity holds**" if verdict["ok"] else "❌ **Parity regression**"
    lines = [f"## Parity: `{algorithm}` on `{phantom}`", "",
             f"{head} — candidate `{candidate}` vs reference `{reference}`, inside the dataset mask.",
             ""]
    for side in ("reference", "candidate"):
        p = provenance.get(side) or {}
        if p:
            lines.append(f"- **{side}**: {' → '.join(f'`{s}`' for s in p.get('chain', []))}"
                         + (f" — image `{p['image']}`" if p.get("image") else "")
                         + (f" — {p['runtime_s']:.0f} s" if p.get("runtime_s") else ""))
    lines.append("")
    lines += ["| Map | Metric | Value | Limit | |", "|---|---|---|---|---|"]
    for name, v in maps.items():
        m = v["metrics"]
        names = BINARY if m.get("kind") == "binary" else CONTINUOUS
        by = {r["metric"]: r for r in v["checks"]}
        first = True
        for metric in list(names) + [k for k in by if k not in names]:
            r = by.get(metric)
            lim = f"{r['op']} {_fmt(r['limit'], metric)}" if r else "—"
            mark = ("" if baseline else ("✅" if r["ok"] else "❌") if r
                    else ("" if v["status"] != "fail" else "❌"))
            val = m.get(metric, r["value"] if r else None)
            lines.append(f"| {'**' + name + '**' if first else ''} | {metric} | {_fmt(val, metric)} "
                         f"| {lim} | {mark} |")
            first = False
        if v["status"] == "fail" and not v["limits"] and not baseline:
            lines.append(f"| | *no limits in parity/thresholds.yml for `{phantom}`* | | | ❌ |")
    if unmatched.get("reference") or unmatched.get("candidate"):
        lines += ["", "Intermediates written by one side only (not compared): "
                  + "; ".join(f"{s}: {', '.join(f'`{n}`' for n in ns)}"
                              for s, ns in unmatched.items() if ns)]
    if baseline:
        sugg = {"datasets": {phantom: {}}}
        ds = sugg["datasets"][phantom]
        for name, v in maps.items():
            lim = derive_limits(v["metrics"])
            if name == provenance.get("final"):
                ds[name] = lim
            else:
                ds.setdefault("intermediates", {})[name] = lim
        lines += ["", "Limits derived from this measurement (paste under the pair in "
                  "`parity/thresholds.yml`):", "", "```yaml",
                  yaml.safe_dump(sugg, sort_keys=False).rstrip(), "```"]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------------------------------
# Running the two sides
# ---------------------------------------------------------------------------------------------------

def _algo(slug: str) -> dict:
    import pipeline
    for a in pipeline.discover_algorithms():
        if a["slug"] == slug:
            return a
    # discover_algorithms drops ci_skip methods; a pair may still name one explicitly.
    raise SystemExit(f"no runnable submission '{slug}' under algorithms/ (missing, or ci_skip)")


def run_side(chain: list, dataset: Path, out: Path, runner: str, feed: "dict | None" = None,
             log=print) -> dict:
    """Run `chain` (slugs, in order) on `dataset`; the last slug's produced artifact lands in
    out/<artifact>.nii.gz and every slug's intermediates in out/intermediates/. Each stage's output
    replaces that artifact as an input of the next, and `feed` ({artifact: path}) overrides inputs
    first. Returns provenance {chain, image, runtime_s, final}."""
    import time
    import pipeline
    from scoring import cli_run_argv, gt_sources
    from qsm_ci.stages import ARTIFACT_FILE
    from qsm_ci.containers import timeout_s

    sources = dict(gt_sources(dataset))
    sources.update(feed or {})
    out.mkdir(parents=True, exist_ok=True)
    inter = out / "intermediates"
    t_all, image, final = 0.0, None, None
    for i, slug in enumerate(chain):
        algo = _algo(slug)
        idir, odir = out / f"_in{i}", out / f"_out{i}"
        pipeline.prepare_input(algo["consumes"], sources, idir)
        odir.mkdir(parents=True, exist_ok=True)
        argv = cli_run_argv(algo, idir, odir, ARTIFACT_FILE, runner) + ["--intermediates", str(inter)]
        limit = timeout_s(algo.get("timeout_minutes"))
        env = {**os.environ, "QSMCI_TIMEOUT": "0" if limit is None else str(limit)}
        log(f"▸ {slug}: {' '.join(argv)}")
        t0 = time.time()
        subprocess.run(argv, env=env, check=True)
        t_all += time.time() - t0
        for art in algo["produces"]:
            sources[art] = odir / ARTIFACT_FILE[art]
        image, final = algo.get("image"), algo["produces"][0]
    import shutil
    shutil.copy(sources[final], out / ARTIFACT_FILE[final])
    prov = {"chain": chain, "image": image, "runtime_s": t_all, "final": final}
    (out / "provenance.json").write_text(json.dumps(prov, indent=2) + "\n")
    return prov


def cmd_run(args) -> int:
    th = load_thresholds(args.thresholds)
    cfg = pair_config(th, args.algorithm)
    ds_cfg = (cfg.get("datasets") or {}).get(args.phantom) or {}
    work = Path(args.work)
    run_side(side_chain(cfg, "reference", args.phantom), Path(args.dataset), work / "reference",
             args.runner)
    # `feed: {totalfield: totalfield}` hands the candidate the reference's intermediate of that name
    # in place of the dataset's artifact, so both reconstruct from the same input. A declared feed
    # whose intermediate the reference did not write is an error, never a silent fallback.
    feed = {}
    for art, name in (ds_cfg.get("feed") or {}).items():
        f = work / "reference" / "intermediates" / f"{name}.nii.gz"
        if not f.exists():
            raise SystemExit(f"feed: {art} <- reference intermediate '{name}', which "
                             f"{cfg['reference']} did not write")
        feed[art] = f
    run_side(side_chain(cfg, "candidate", args.phantom), Path(args.dataset), work / "candidate",
             args.runner, feed=feed)
    return 0


def _load(path: Path):
    import nibabel as nib
    import numpy as np
    return np.asanyarray(nib.load(str(path)).dataobj)


def compare_dirs(ref_dir: Path, cand_dir: Path, mask_path: Path, final: str) -> "tuple[dict, dict]":
    """({name: metrics}, unmatched) for the final artifact and the intermediates both sides wrote."""
    from qsm_ci.stages import ARTIFACT_FILE
    mask = _load(mask_path)
    results = {final: compare_maps(_load(ref_dir / ARTIFACT_FILE[final]),
                                   _load(cand_dir / ARTIFACT_FILE[final]), mask)}
    names = {s: {p.name[:-7] for p in (d / "intermediates").glob("*.nii.gz")}
             for s, d in (("reference", ref_dir), ("candidate", cand_dir))}
    for name in sorted(names["reference"] & names["candidate"]):
        results[name] = compare_maps(_load(ref_dir / "intermediates" / f"{name}.nii.gz"),
                                     _load(cand_dir / "intermediates" / f"{name}.nii.gz"), mask)
    unmatched = {"reference": sorted(names["reference"] - names["candidate"]),
                 "candidate": sorted(names["candidate"] - names["reference"])}
    return results, unmatched


def cmd_compare(args) -> int:
    th = load_thresholds(args.thresholds)
    cfg = pair_config(th, args.algorithm)
    ds_cfg = (cfg.get("datasets") or {}).get(args.phantom) or {}
    work = Path(args.work)
    prov = {s: json.loads((work / s / "provenance.json").read_text())
            if (work / s / "provenance.json").exists() else {} for s in ("reference", "candidate")}
    final = prov["reference"].get("final") or "chimap"
    mask = Path(args.mask) if args.mask else Path(args.dataset) / "inputs" / "mask.nii.gz"
    results, unmatched = compare_dirs(work / "reference", work / "candidate", mask, final)
    verdict = evaluate(results, ds_cfg, final)
    report = render_report(algorithm=args.algorithm, phantom=args.phantom,
                           reference=cfg["reference"], candidate=cfg["candidate"], verdict=verdict,
                           baseline=args.baseline, unmatched=unmatched,
                           provenance={**prov, "final": final})
    print(report)
    if args.report:
        Path(args.report).write_text(report)
    if args.json:
        Path(args.json).write_text(json.dumps({
            "algorithm": args.algorithm, "phantom": args.phantom, "reference": cfg["reference"],
            "candidate": cfg["candidate"], "baseline": args.baseline, "provenance": prov,
            "unmatched": unmatched, **verdict,
            "suggested": {n: derive_limits(v["metrics"]) for n, v in verdict["maps"].items()},
        }, indent=2, default=str) + "\n")
    return 0 if (args.baseline or verdict["ok"]) else 1


def cmd_pairs(args) -> int:
    th = load_thresholds(args.thresholds)
    if args.matrix:
        print(json.dumps(plan_matrix(th, args.algorithm, args.dataset)))
    else:
        print(json.dumps(pair_listing(discover_pairs(), th), indent=2))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--thresholds", type=Path, default=THRESHOLDS)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("pairs", help="list pairs (or print the workflow matrix with --matrix)")
    p.add_argument("--matrix", action="store_true")
    p.add_argument("--algorithm", default="enabled")
    p.add_argument("--dataset", default="configured")
    p.set_defaults(fn=cmd_pairs)
    for name, fn in (("run", cmd_run), ("compare", cmd_compare)):
        p = sub.add_parser(name)
        p.add_argument("--algorithm", required=True)
        p.add_argument("--phantom", default="sim", help="scripts/datasets.json key (thresholds key)")
        p.add_argument("--dataset", required=True, type=Path, help="dataset dir (inputs/, groundtruth/)")
        p.add_argument("--work", required=True, type=Path)
        p.set_defaults(fn=fn)
        if name == "run":
            p.add_argument("--runner", default="docker", choices=["docker", "podman", "apptainer", "local"])
        else:
            p.add_argument("--mask", type=Path, help="default: <dataset>/inputs/mask.nii.gz")
            p.add_argument("--baseline", action="store_true",
                           help="measure and suggest limits; never fail on them")
            p.add_argument("--report", type=Path)
            p.add_argument("--json", type=Path)
    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
