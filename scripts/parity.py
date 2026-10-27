#!/usr/bin/env python3
"""Port parity: run two implementations of one algorithm on the same dataset and check they agree.

A *pair* is two submissions with the same `algorithm:` in algorithm.yml: an original (any source but
qsmrs), the `reference`, and the QSM.rs port (`source: qsmrs`), the `candidate` — e.g.
qsmart-matlab vs qsmart-qsmrs. An algorithm may have several originals (an STI Suite and a Julia
one, say): `parity/thresholds.yml` names the reference of each pair explicitly, so there is no rule
to guess which original counts. It also says which pairs are enabled and the limits each comparison
must stay inside on each dataset (see the comments there).

`run --qsmrs-image REF` runs every QSM.rs step (`source: qsmrs`) in REF instead of the image its
algorithm.yml pins: that is how the workflow checks a QSM.rs/QSMxT build that is not released yet.

Subcommands (the `parity` workflow runs them in this order):

  pairs    list the pairs algorithm.yml defines and whether each is enabled, as JSON (`--matrix`
           prints the workflow's job matrix for an algorithm/dataset selection instead).
  run      run the reference and then the candidate on one dataset through `qsm-ci run` (the same
           run path score.yml uses), collecting each side's produced artifact and its intermediates.
  compare  compare the two sides inside the dataset mask — the final artifact and every
           intermediate both sides wrote under the same name — against the thresholds, write a
           markdown report and a JSON result, and exit 1 if any limit is exceeded.
  report   collect a run's per-job results into one record per pair × dataset (what was checked,
           against which QSM.rs commit and images, the verdict and metrics) and write the run's
           summary: which pairs passed against exactly the QSM.rs commit under test.
  record   append a run's records to parity/results.json, the history `status` reads.
  status   say, per pair, when it was last checked, against which QSM.rs, with what result, and
           whether that check is stale (see `staleness`); writes parity/status.json, the table in
           parity/STATUS.md and the tracking issue's body.

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


def load_settings(path: Path = THRESHOLDS) -> dict:
    """thresholds.yml's top-level settings (everything but `pairs`), with defaults."""
    doc = yaml.safe_load(Path(path).read_text()) or {}
    out = {"stale_after_days": 90, "qsmrs_repo": "astewartau/QSM.rs", "qsmrs_branch": "main"}
    out.update({k: v for k, v in doc.items() if k != "pairs"})
    return out


def _manifests(algorithms_dir: Path = ROOT / "algorithms") -> dict:
    """{slug: algorithm.yml} for every submission folder (ci_skip ones included)."""
    out = {}
    for spec in sorted(Path(algorithms_dir).glob("*/algorithm.yml")):
        if spec.parent.name.startswith("_"):
            continue
        try:
            out[spec.parent.name] = yaml.safe_load(spec.read_text()) or {}
        except yaml.YAMLError:
            continue
    return out


def is_port(doc: dict) -> bool:
    return str(doc.get("source", "")) == "qsmrs"


def discover_pairs(algorithms_dir: Path = ROOT / "algorithms") -> dict:
    """{algorithm: {"original": [slugs], "port": [slugs]}} for every `algorithm:` that has both a
    QSM.rs port (`source: qsmrs`) and at least one other implementation. Skipped (`ci_skip`) methods
    are kept: whether a pair runs is thresholds.yml's call, and the listing should show it exists."""
    groups: dict = {}
    for slug, doc in _manifests(algorithms_dir).items():
        alg = doc.get("algorithm")
        if alg:
            side = "port" if is_port(doc) else "original"
            groups.setdefault(str(alg), {"original": [], "port": []})[side].append(slug)
    return {a: g for a, g in groups.items() if g["original"] and g["port"]}


def pair_problems(name: str, cfg: dict, manifests: dict) -> list:
    """Why a thresholds.yml pair is not a pair of algorithm.yml entries ([] when it is): the
    reference must be an original and the candidate a QSM.rs port of the same `algorithm:`."""
    ref, cand = (cfg or {}).get("reference"), (cfg or {}).get("candidate")
    if not ref or not cand:
        return [f"{name}: needs reference: and candidate:"]
    probs = [f"{name}: no algorithms/{s}/algorithm.yml" for s in (ref, cand) if s not in manifests]
    if probs:
        return probs
    r, c = manifests[ref], manifests[cand]
    if is_port(r):
        probs.append(f"{name}: reference {ref} is a QSM.rs port (source: qsmrs), not an original")
    if not is_port(c):
        probs.append(f"{name}: candidate {cand} is not a QSM.rs port (source: qsmrs)")
    if r.get("algorithm") != c.get("algorithm"):
        probs.append(f"{name}: {ref} is algorithm {r.get('algorithm')!r} but {cand} is "
                     f"{c.get('algorithm')!r}; a pair shares one algorithm:")
    return probs


def pair_listing(pairs: dict, thresholds: dict, manifests: "dict | None" = None) -> list:
    """One row per configured pair (with `problems` if it no longer matches algorithm.yml), then one
    per algorithm that has an original and a port but no pair configured."""
    manifests = _manifests() if manifests is None else manifests
    rows, covered = [], set()
    for name, cfg in sorted(thresholds.items()):
        cfg = cfg or {}
        alg = (manifests.get(cfg.get("candidate")) or {}).get("algorithm")
        covered.add(alg)
        rows.append({"pair": name, "algorithm": alg, "reference": cfg.get("reference"),
                     "candidate": cfg.get("candidate"), "enabled": bool(cfg.get("enabled")),
                     **({"blocked_by": cfg["blocked_by"]} if cfg.get("blocked_by") else {}),
                     "datasets": sorted((cfg.get("datasets") or {}).keys()),
                     "problems": pair_problems(name, cfg, manifests)})
    for alg, g in sorted(pairs.items()):
        if alg not in covered:
            rows.append({"pair": None, "algorithm": alg, "originals": g["original"],
                         "ports": g["port"], "enabled": False, "datasets": []})
    return rows


SELECTORS = ("enabled", "all-configured")


def _tokens(s: str) -> list:
    return [t for t in str(s or "").replace(",", " ").split() if t]


def select_pairs(thresholds: dict, algorithm: str) -> list:
    """The pairs an `algorithm` selection names, in thresholds.yml order, without duplicates.

    `algorithm` is a comma- (or space-) separated list of pair names and the selectors `enabled`
    (every enabled pair) and `all-configured` (every pair with at least one dataset configured,
    enabled or not). Any name that is not a pair is an error, before anything runs."""
    toks = _tokens(algorithm)
    if not toks:
        raise SystemExit("algorithm: name one or more pairs (comma-separated), 'enabled' or "
                         "'all-configured'")
    unknown = [t for t in toks if t not in SELECTORS and t not in thresholds]
    if unknown:
        raise SystemExit(f"algorithm: no pair {', '.join(repr(u) for u in unknown)} in "
                         f"parity/thresholds.yml (pairs: {', '.join(thresholds)}; or "
                         f"{' / '.join(SELECTORS)})")
    picked = set()
    for t in toks:
        if t == "enabled":
            picked |= {a for a, c in thresholds.items() if (c or {}).get("enabled")}
        elif t == "all-configured":
            picked |= {a for a, c in thresholds.items() if (c or {}).get("datasets")}
        else:
            picked.add(t)
    return [a for a in thresholds if a in picked]


def _route(slugs: list, algorithms_dir: Path) -> dict:
    """Runner and job cap for a job that runs `slugs` one after another: the most demanding of
    their tiers (scripts/score_plan.route; a self-hosted method takes the job self-hosted), with the
    caps added up for the hosted tiers, which stop at GitHub's 360 min."""
    import score_plan
    routes = [score_plan.route(score_plan.load_spec(algorithms_dir, s)) for s in slugs]
    selfh = [r for r in routes if r["runs_on"] != "ubuntu-latest"]
    if selfh:
        return {"runs_on": selfh[0]["runs_on"], "timeout": max(r["timeout"] for r in selfh)}
    return {"runs_on": "ubuntu-latest", "timeout": 360}


def plan_matrix(thresholds: dict, algorithm: str, dataset: str,
                manifests: "dict | None" = None, datasets: "dict | None" = None,
                algorithms_dir: Path = ROOT / "algorithms") -> list:
    """The workflow's job matrix: one {algorithm, phantom, runs_on, timeout} per selected pair ×
    dataset.

    `algorithm` is a selection (select_pairs). `dataset` is one or more dataset keys
    (comma-separated) or `configured` (every dataset each pair has a thresholds entry for). Naming a
    disabled pair explicitly still runs it — that is how a new pair gets its first baseline.

    Everything is validated before a job starts: each selected pair must still match algorithm.yml
    (pair_problems) and each dataset must be a scripts/datasets.json key. `manifests` / `datasets`
    default to the repo's; pass {} to skip a check (unit tests)."""
    algs = select_pairs(thresholds, algorithm)
    manifests = _manifests(algorithms_dir) if manifests is None else manifests
    if datasets is None:
        datasets = json.loads((ROOT / "scripts" / "datasets.json").read_text())
    probs = [p for a in algs for p in pair_problems(a, thresholds[a], manifests)] if manifests else []
    if probs:
        raise SystemExit("parity/thresholds.yml: " + "; ".join(probs))
    out = []
    for a in algs:
        cfg = thresholds[a] or {}
        dss = sorted((cfg.get("datasets") or {}).keys()) if dataset == "configured" \
            else _tokens(dataset)
        if not dss:
            dss = ["sim"]
        bad = [d for d in dss if datasets and d not in datasets]
        if bad:
            raise SystemExit(f"dataset: {', '.join(bad)} not in scripts/datasets.json")
        for d in dss:
            route = _route(side_chain(cfg, "reference", d) + side_chain(cfg, "candidate", d),
                           algorithms_dir) if manifests else {"runs_on": "ubuntu-latest",
                                                              "timeout": 360}
            out.append({"algorithm": a, "phantom": d, **route})
    return out


def pair_config(thresholds: dict, algorithm: str, manifests: "dict | None" = None,
                validate: bool = True) -> dict:
    """A pair's thresholds.yml entry. `validate` also checks it against algorithm.yml (before a
    run; `compare` works on outputs already written and needs only the names)."""
    cfg = thresholds.get(algorithm)
    if cfg is None:
        raise SystemExit(f"no pair '{algorithm}' in parity/thresholds.yml")
    if not validate:
        manifests = {s: {"algorithm": "x", "source": "qsmrs" if s == cfg.get("candidate") else "o"}
                     for s in (cfg.get("reference"), cfg.get("candidate")) if s}
    probs = pair_problems(algorithm, cfg, _manifests() if manifests is None else manifests)
    if probs:
        raise SystemExit("parity/thresholds.yml: " + "; ".join(probs))
    return cfg


def side_chain(cfg: dict, side: str, phantom: str) -> list:
    """The slugs one side runs, in order. Normally just the reference/candidate slug; a dataset entry
    may prefix it (`<side>_prefix: [laplacian-qsmrs]`) when the dataset lacks the stage boundary that
    side consumes — e.g. an in-vivo acquisition with no ground-truth total field."""
    ds = (cfg.get("datasets") or {}).get(phantom) or {}
    return list(ds.get(f"{side}_prefix") or []) + [cfg[side]]


def side_set(cfg: dict, side: str, phantom: str) -> dict:
    """The `--set` overrides one side's own method runs with: the pair's `<side>_set`, then the
    dataset entry's (which wins). This is how a pair runs both implementations with matched
    settings when their defaults differ (e.g. QSM.jl's padding off, as QSM.rs; or a value that
    depends on the dataset's field strength and echo time). Prefix steps run with their defaults."""
    ds = (cfg.get("datasets") or {}).get(phantom) or {}
    return {**(cfg.get(f"{side}_set") or {}), **(ds.get(f"{side}_set") or {})}


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
                  baseline: bool, unmatched: dict, provenance: dict, note: str = "") -> str:
    maps = verdict["maps"]
    if baseline:
        head = "📏 **Baseline measured** (no limits applied)"
    else:
        head = "✅ **Parity holds**" if verdict["ok"] else "❌ **Parity regression**"
    lines = [f"## Parity: `{algorithm}` on `{phantom}`", "",
             f"{head} — candidate `{candidate}` vs reference `{reference}`, inside the dataset mask.",
             ""] + ([note, ""] if note else [])
    for side in ("reference", "candidate"):
        p = provenance.get(side) or {}
        if not p:
            continue
        lines.append(f"- **{side}**: {' → '.join(f'`{s}`' for s in p.get('chain', []))}"
                     + (f" — {p['runtime_s']:.0f} s" if p.get("runtime_s") else ""))
        for st in p.get("steps") or [{"slug": (p.get("chain") or ["?"])[-1], "image": p.get("image")}]:
            bits = [f"image `{st['image']}`"] if st.get("image") else []
            bits += [f"`{st['qsmxt']}`"] if st.get("qsmxt") else []
            bits += [f"ID `{st['id'][:19]}`"] if st.get("id") else []
            bits += [f"fed the reference's {', '.join(f'`{a}`' for a in st['fed'])}"] \
                if st.get("fed") else []
            bits += [f"`--set {' '.join(f'{k}={v}' for k, v in st['set'].items())}`"] \
                if st.get("set") else []
            if bits:
                lines.append(f"  - `{st['slug']}`: " + ", ".join(bits))
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

def _algo(slug: str, qsmrs_image: "str | None" = None) -> dict:
    """A submission as the scorer runs it (pipeline.discover_algorithms), including one that
    scoring skips: a pair names its two sides explicitly, and `ci_skip` / `parity_only` only take a
    method out of scoring.

    One case cannot run: a `ci_skip` QSM.rs port with no image under test. Such a port is skipped
    because the qsmxt release its algorithm.yml pins lacks it (e.g. star-qsmrs before a release
    with `qsmxt invert star`); a qsmxt built from source (`--qsmrs-image`) runs it."""
    import pipeline
    doc = _manifests().get(slug)
    if doc is not None and doc.get("ci_skip") and is_port(doc) and not qsmrs_image:
        raise SystemExit(f"{slug} is ci_skip: the qsmxt image its algorithm.yml pins cannot run "
                         f"it. Run it against a qsmxt build (workflow: qsmrs_ref / qsmxt_ref / "
                         f"qsmxt_image; here: --qsmrs-image)")
    for a in pipeline.discover_algorithms(include={slug}):
        if a["slug"] == slug:
            return a
    raise SystemExit(f"no runnable submission '{slug}' under algorithms/")


def image_identity(image: "str | None", runner: str) -> dict:
    """What an image is, for the report: its ID and, for a qsmxt image, `qsmxt --version`. Empty
    for the `local` runner or an image the engine cannot inspect."""
    if not image or runner not in ("docker", "podman"):
        return {}
    out = {}
    r = subprocess.run([runner, "image", "inspect", "--format", "{{.Id}}", image],
                       capture_output=True, text=True)
    if r.returncode == 0:
        out["id"] = r.stdout.strip()
    r = subprocess.run([runner, "run", "--rm", "--network", "none", "--entrypoint", "qsmxt", image,
                        "--version"], capture_output=True, text=True)
    if r.returncode == 0 and r.stdout.strip():
        out["qsmxt"] = r.stdout.strip().splitlines()[0]
        out.update(parse_qsmrs_version(r.stdout))
    return out


def parse_qsmrs_version(text: str) -> dict:
    """The QSM.rs a qsmxt binary was built with, from its `--version` output (the line
    `QSM.rs (qsm-core): v0.39.0 (42ab6201…)`): {"qsmrs_version", "qsmrs_commit"}, or {}."""
    import re
    m = re.search(r"qsm-core\)?:\s*v?([0-9][^\s(]*)\s*\(([0-9a-f]{7,40})\)", text or "")
    return {"qsmrs_version": m.group(1), "qsmrs_commit": m.group(2)} if m else {}


def apply_names(inter: Path, names: "dict | None", mask_path: "Path | None" = None) -> None:
    """Rename a side's intermediates to the names they are compared under (CONTRACT.md,
    "Intermediates"), for a method whose own names differ — e.g. a compiled MATLAB image that
    predates the convention. `names` is {native: canonical} or {native: {name: canonical,
    complement: true}}; `complement` turns a mask into its complement inside the dataset mask (the
    original's `vasc_only` is tissue without vessels; `vessel_mask` is the vessels)."""
    for native, spec in (names or {}).items():
        src = inter / f"{native}.nii.gz"
        if not src.exists():
            continue
        spec = spec if isinstance(spec, dict) else {"name": spec}
        dst = inter / f"{spec['name']}.nii.gz"
        if spec.get("complement"):
            import nibabel as nib
            import numpy as np
            img = nib.load(str(src))
            m = _load(mask_path) > 0.5
            out = (m & (np.asanyarray(img.dataobj) < 0.5)).astype(np.uint8)
            nib.save(nib.Nifti1Image(out, img.affine, img.header), str(dst))
            src.unlink()
        else:
            src.replace(dst)


def run_side(chain: list, dataset: Path, out: Path, runner: str, feed: "dict | None" = None,
             qsmrs_image: "str | None" = None, names: "dict | None" = None,
             overrides: "dict | None" = None, log=print) -> dict:
    """Run `chain` (slugs, in order) on `dataset`; the last slug's produced artifact lands in
    out/<artifact>.nii.gz and every slug's intermediates in out/intermediates/. Each stage's output
    replaces that artifact as an input of the next, and is also kept as an intermediate under the
    artifact's name (e.g. a field-mapping prefix's `totalfield`) unless the method wrote one itself.
    `feed` ({artifact: path}) overrides inputs first; `qsmrs_image` replaces the image of every
    QSM.rs step; `names` renames the intermediates afterwards (apply_names); `overrides` are the
    `--set` values for the chain's last slug, the pair's own method (side_set).
    Returns provenance {chain, steps: [{slug, image, …}], image, runtime_s, final}."""
    import shutil
    import time
    import pipeline
    from scoring import cli_run_argv, gt_sources
    from qsm_ci.stages import ARTIFACT_FILE
    from qsm_ci.containers import timeout_s

    sources = dict(gt_sources(dataset))
    sources.update(feed or {})
    if feed:
        first = _algo(chain[0], qsmrs_image)
        stray = sorted(set(feed) - set(first["consumes"]))
        if stray:
            raise SystemExit(f"feed: {chain[0]} does not consume {', '.join(stray)}")
    out.mkdir(parents=True, exist_ok=True)
    inter = out / "intermediates"
    inter.mkdir(exist_ok=True)
    t_all, final, steps = 0.0, None, []
    for i, slug in enumerate(chain):
        algo = _algo(slug, qsmrs_image)
        idir, odir = out / f"_in{i}", out / f"_out{i}"
        pipeline.prepare_input(algo["consumes"], sources, idir)
        odir.mkdir(parents=True, exist_ok=True)
        sets = dict(overrides or {}) if i == len(chain) - 1 else {}
        argv = cli_run_argv(algo, idir, odir, ARTIFACT_FILE, runner, overrides=sets) \
            + ["--intermediates", str(inter)]
        image = algo.get("image")
        # discover_algorithms() keeps no `source`: read it from algorithm.yml.
        if qsmrs_image and is_port(_manifests().get(slug) or {}):
            image = qsmrs_image
            argv += ["--image", qsmrs_image]
        limit = timeout_s(algo.get("timeout_minutes"))
        env = {**os.environ, "QSMCI_TIMEOUT": "0" if limit is None else str(limit)}
        log(f"▸ {slug}: {' '.join(argv)}")
        t0 = time.time()
        subprocess.run(argv, env=env, check=True)
        dt = time.time() - t0
        t_all += dt
        for art in algo["produces"]:
            sources[art] = odir / ARTIFACT_FILE[art]
            if i < len(chain) - 1 and not (inter / ARTIFACT_FILE[art]).exists():
                shutil.copy(sources[art], inter / ARTIFACT_FILE[art])
        final = algo["produces"][0]
        steps.append({"slug": slug, "image": image, "runtime_s": dt,
                      **({"fed": sorted(feed)} if feed and i == 0 else {}),
                      **({"set": sets} if sets else {}),
                      **image_identity(image, runner)})
    shutil.copy(sources[final], out / ARTIFACT_FILE[final])
    apply_names(inter, names, Path(dataset) / "inputs" / "mask.nii.gz")
    prov = {"chain": chain, "steps": steps, "image": steps[-1]["image"], "runtime_s": t_all,
            "final": final}
    (out / "provenance.json").write_text(json.dumps(prov, indent=2) + "\n")
    return prov


def cmd_run(args) -> int:
    th = load_thresholds(args.thresholds)
    cfg = pair_config(th, args.algorithm)
    ds_cfg = (cfg.get("datasets") or {}).get(args.phantom) or {}
    work = Path(args.work)
    run_side(side_chain(cfg, "reference", args.phantom), Path(args.dataset), work / "reference",
             args.runner, qsmrs_image=args.qsmrs_image or None, names=cfg.get("reference_names"),
             overrides=side_set(cfg, "reference", args.phantom))
    # `feed: {totalfield: totalfield}` hands the candidate the reference's intermediate of that name
    # (after reference_names) in place of the dataset's artifact, so both reconstruct from the same
    # input. A declared feed whose intermediate the reference did not write is an error, never a
    # silent fallback.
    feed = {}
    for art, name in (ds_cfg.get("feed") or {}).items():
        f = work / "reference" / "intermediates" / f"{name}.nii.gz"
        if not f.exists():
            raise SystemExit(f"feed: {art} <- reference intermediate '{name}', which "
                             f"{cfg['reference']} did not write")
        feed[art] = f
    run_side(side_chain(cfg, "candidate", args.phantom), Path(args.dataset), work / "candidate",
             args.runner, feed=feed, qsmrs_image=args.qsmrs_image or None,
             names=cfg.get("candidate_names"), overrides=side_set(cfg, "candidate", args.phantom))
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
    for s in names.values():
        s.discard(final)   # a copy of the final map (QSMART's recon writes one) is not a step
    for name in sorted(names["reference"] & names["candidate"]):
        results[name] = compare_maps(_load(ref_dir / "intermediates" / f"{name}.nii.gz"),
                                     _load(cand_dir / "intermediates" / f"{name}.nii.gz"), mask)
    unmatched = {"reference": sorted(names["reference"] - names["candidate"]),
                 "candidate": sorted(names["candidate"] - names["reference"])}
    return results, unmatched


def cmd_compare(args) -> int:
    th = load_thresholds(args.thresholds)
    cfg = pair_config(th, args.algorithm, validate=False)
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
                           provenance={**prov, "final": final}, note=args.note)
    print(report)
    if args.report:
        Path(args.report).write_text(report)
    if args.json:
        Path(args.json).write_text(json.dumps({
            "algorithm": args.algorithm, "phantom": args.phantom, "reference": cfg["reference"],
            "candidate": cfg["candidate"], "baseline": args.baseline, "provenance": prov,
            "note": args.note,
            "unmatched": unmatched, **verdict,
            "suggested": {n: derive_limits(v["metrics"]) for n, v in verdict["maps"].items()},
        }, indent=2, default=str) + "\n")
    return 0 if (args.baseline or verdict["ok"]) else 1


# ---------------------------------------------------------------------------------------------------
# Run history (parity/results.json) and staleness (parity/status.json, parity/STATUS.md)
# ---------------------------------------------------------------------------------------------------

RESULTS = ROOT / "parity" / "results.json"
STATUS_JSON = ROOT / "parity" / "status.json"
STATUS_MD = ROOT / "parity" / "STATUS.md"
HISTORY_PER_CHECK = 50   # records kept per pair × dataset in results.json
REPO = "QSMxT/QSM-CI"

# The pair settings that decide what a check measures and how it is judged. A change to any of them
# (or to the dataset's entry, limits included) makes the last check stale (rule c). `measured`,
# `enabled`, `blocked_by` and `qsmrs_paths` are bookkeeping and do not count.
MEASURED_BY = ("reference", "candidate", "reference_names", "candidate_names", "reference_set",
               "candidate_set")


def thresholds_version(cfg: dict, phantom: str) -> str:
    """A short hash of what a pair × dataset check measures and the limits it is held to."""
    import hashlib
    ds = dict(((cfg or {}).get("datasets") or {}).get(phantom) or {})
    ds.pop("measured", None)
    blob = {k: cfg.get(k) for k in MEASURED_BY if cfg.get(k) is not None}
    blob["dataset"] = ds
    return hashlib.sha256(json.dumps(blob, sort_keys=True, default=str).encode()).hexdigest()[:12]


def image_digest(image: "str | None") -> "str | None":
    """`sha256:…` of an image pinned by digest (`repo@sha256:…`), else None."""
    if image and "@sha256:" in image:
        return image.split("@", 1)[1].split()[0]
    return None


def make_record(res: "dict | None", *, pair: str, phantom: str, cfg: dict, manifests: dict,
                run: dict, build: "dict | None" = None) -> dict:
    """One results.json record for a pair × dataset job of a run.

    `res` is the job's parity.json (None when the job ended before `compare`: an error, which
    counts as a failed check). `run` holds the run's date, id, URL, QSM-CI commit and the
    qsmrs_ref / qsmxt_ref it was dispatched with; `build` is the qsmxt job's built.json when the
    run built one. The QSM.rs commit is what the candidate's own qsmxt reports (`qsmxt --version`),
    so a pinned image is recorded as exactly as a build."""
    ref_slug, cand_slug = cfg.get("reference"), cfg.get("candidate")
    ref_image = (manifests.get(ref_slug) or {}).get("image")
    build = build or {}
    rec = {"pair": pair, "dataset": phantom, "date": run.get("date"),
           "run_id": run.get("run_id"), "run_url": run.get("run_url"),
           "qsmci_commit": run.get("qsmci_commit"),
           "thresholds": thresholds_version(cfg, phantom),
           "reference": {"slug": ref_slug, "image": ref_image, "digest": image_digest(ref_image)},
           "candidate": {"slug": cand_slug},
           "qsmrs": {"ref": run.get("qsmrs_ref") or None, "commit": build.get("qsmrs_commit"),
                     "version": build.get("qsmrs_version")},
           "qsmxt": {"ref": build.get("qsmxt_ref") or run.get("qsmxt_ref") or None,
                     "commit": build.get("qsmxt_commit")}}
    if res is None:
        rec["result"] = "error"
        rec["failed"] = ["no comparison: the job failed or was cancelled before `compare` ran"]
        return rec
    prov = res.get("provenance") or {}
    cst = ((prov.get("candidate") or {}).get("steps") or [{}])[-1]
    rst = ((prov.get("reference") or {}).get("steps") or [{}])[-1]
    rec["candidate"].update({"image": cst.get("image"),
                             "digest": image_digest(cst.get("image")) or cst.get("id"),
                             "qsmxt": cst.get("qsmxt")})
    if rst.get("id"):
        rec["reference"]["id"] = rst["id"]
    if cst.get("qsmrs_commit"):
        rec["qsmrs"].update(commit=cst["qsmrs_commit"], version=cst.get("qsmrs_version"))
    if cst.get("set") or rst.get("set"):
        rec["set"] = {k: v for k, v in (("reference", rst.get("set")),
                                        ("candidate", cst.get("set"))) if v}
    maps = res.get("maps") or {}
    rec["result"] = "baseline" if res.get("baseline") else ("pass" if res.get("ok") else "fail")
    rec["metrics"] = {n: {k: v["metrics"][k] for k in ("kind",) + CONTINUOUS + BINARY + ("nonfinite",)
                          if k in v["metrics"]} for n, v in maps.items()}
    failed = []
    for n, v in maps.items():
        if v.get("status") == "fail" and not v.get("limits"):
            failed.append(f"{n}: no limits for this dataset")
        failed += [f"{n} {r['metric']} {_fmt(r['value'], r['metric'])} (limit {r['op']} "
                   f"{_fmt(r['limit'], r['metric'])})" for r in v.get("checks") or [] if not r["ok"]]
    if failed and rec["result"] != "baseline":
        rec["failed"] = failed
    return rec


def load_results(path: Path = RESULTS) -> dict:
    p = Path(path)
    doc = json.loads(p.read_text()) if p.exists() and p.read_text().strip() else {}
    return {"schema": 1, "checks": list(doc.get("checks") or [])}


def merge_records(results: dict, records: list, keep: int = HISTORY_PER_CHECK) -> dict:
    """results.json with `records` added: a record replaces one from the same run, pair and
    dataset (re-recording a run is a no-op), baselines are left out (they apply no limits), and each
    pair × dataset keeps its `keep` newest records."""
    key = lambda r: (r.get("run_id"), r.get("pair"), r.get("dataset"))   # noqa: E731
    new = [r for r in records if r.get("result") != "baseline"]
    seen = {key(r) for r in new}
    checks = [r for r in results.get("checks") or [] if key(r) not in seen] + new
    checks.sort(key=lambda r: (r.get("pair") or "", r.get("dataset") or "", r.get("date") or ""))
    out, count = [], {}
    for r in reversed(checks):
        k = (r.get("pair"), r.get("dataset"))
        count[k] = count.get(k, 0) + 1
        if count[k] <= keep:
            out.append(r)
    return {"schema": 1, "checks": list(reversed(out))}


def latest_records(results: dict) -> dict:
    """{(pair, dataset): newest record}."""
    out = {}
    for r in results.get("checks") or []:
        k = (r.get("pair"), r.get("dataset"))
        if k not in out or (r.get("date") or "") >= (out[k].get("date") or ""):
            out[k] = r
    return out


def _short(sha: "str | None", n: int = 7) -> str:
    return (sha or "")[:n] or "?"


def _qsmrs_label(rec: "dict | None") -> str:
    q = (rec or {}).get("qsmrs") or {}
    if not q.get("commit"):
        return "unknown"
    return (f"v{q['version']} " if q.get("version") else "") + f"`{_short(q['commit'])}`"


def refresh_command(pairs: list, qsmrs_ref: str = "main") -> str:
    return (f"gh workflow run parity.yml -R {REPO} -f algorithm={','.join(pairs)} "
            f"-f dataset=configured -f qsmrs_ref={qsmrs_ref}")


def github_compare(repo: str, base: str, head: str, token: "str | None" = None) -> dict:
    """The files changed on `head` since `base` (GitHub's compare API, from their merge base):
    {"ahead_by", "files"} or {"error"}. The API lists at most 300 files; `truncated` says so."""
    import urllib.error
    import urllib.request
    url = f"https://api.github.com/repos/{repo}/compare/{base}...{head}?per_page=100"
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json",
                                               **({"Authorization": f"Bearer {token}"}
                                                  if token else {})})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            doc = json.load(r)
    except urllib.error.HTTPError as e:
        return {"error": f"compare {_short(base)}...{head}: HTTP {e.code}",
                "unknown_commit": e.code == 404}
    except (urllib.error.URLError, TimeoutError) as e:
        return {"error": f"compare {_short(base)}...{head}: {e}"}
    files = set()
    for f in doc.get("files") or []:
        files.add(f.get("filename"))
        if f.get("previous_filename"):
            files.add(f["previous_filename"])
    return {"ahead_by": doc.get("ahead_by", 0), "files": sorted(x for x in files if x),
            "truncated": len(doc.get("files") or []) >= 300}


def touched(files: list, paths: list) -> list:
    """The files under any of `paths` (a file, or a directory prefix)."""
    ps = [p.rstrip("/") for p in paths or []]
    return [f for f in files if any(f == p or f.startswith(p + "/") for p in ps)]


def staleness(rec: "dict | None", cfg: dict, phantom: str, manifests: dict, settings: dict,
              today: str, changes=None) -> list:
    """Why the last check of a pair on a dataset no longer stands ([] when it does):

      (a) the reference image pinned in algorithm.yml is not the one last checked;
      (b) QSM.rs `main` has commits touching the pair's `qsmrs_paths` since the QSM.rs commit last
          checked (`changes(commit)` returns github_compare's answer; None skips this rule);
      (c) the pair's settings or limits for the dataset changed since (thresholds_version);
      (d) it was never checked, or last checked more than `stale_after_days` ago;
      (e) the last check failed (or ended without a result)."""
    from datetime import date
    if rec is None:
        return ["never checked"]
    why = []
    ref_now = image_digest((manifests.get(cfg.get("reference")) or {}).get("image"))
    ref_then = ((rec.get("reference") or {}).get("digest"))
    if ref_now != ref_then:
        why.append(f"reference image changed: checked {_short(ref_then, 19)}, algorithm.yml "
                   f"pins {_short(ref_now, 19)}")
    commit = (rec.get("qsmrs") or {}).get("commit")
    if changes is not None:
        if not commit:
            why.append("the QSM.rs commit of the last check is not recorded")
        else:
            c = changes(commit) or {}
            if c.get("error"):
                if c.get("unknown_commit"):
                    why.append(f"the checked QSM.rs commit {_short(commit)} is not in "
                               f"{settings['qsmrs_repo']}")
            else:
                hit = touched(c.get("files") or [], cfg.get("qsmrs_paths") or [])
                if hit:
                    shown = ", ".join(f"`{f}`" for f in hit[:4]) + (" …" if len(hit) > 4 else "")
                    why.append(f"QSM.rs {settings['qsmrs_branch']} changed {shown} since the "
                               f"checked {_short(commit)} ({c.get('ahead_by', '?')} commits)")
    if rec.get("thresholds") != thresholds_version(cfg, phantom):
        why.append("the pair's settings or limits for this dataset changed since")
    n = int(settings.get("stale_after_days") or 90)
    try:
        age = (date.fromisoformat(today[:10]) - date.fromisoformat((rec.get("date") or "")[:10])).days
    except ValueError:
        age = None
    if age is None or age > n:
        why.append(f"last checked {age if age is not None else '?'} days ago (limit {n})")
    if rec.get("result") == "error":
        why.append("the last check ended without a result")
    elif rec.get("result") != "pass":
        why.append("the last check failed" + (f": {rec['failed'][0]}" if rec.get("failed") else ""))
    return why


def pair_status(thresholds: dict, results: dict, manifests: dict, settings: dict, today: str,
                changes=None) -> list:
    """One row per configured pair: its state and, per dataset, the last check and why it is
    stale. State: `current` (enabled, every dataset's last check stands), `stale`, `gap` (disabled
    and `blocked_by` a known gap: the port does not match its original yet), `off` (disabled: not
    verified or not measured yet)."""
    last = latest_records(results)
    cache: dict = {}

    def cached(commit):
        if changes is None:
            return None
        if commit not in cache:
            cache[commit] = changes(commit)
        return cache[commit]

    rows = []
    for name, cfg in thresholds.items():
        cfg = cfg or {}
        enabled = bool(cfg.get("enabled"))
        dss = []
        for ds in sorted((cfg.get("datasets") or {}).keys()):
            rec = last.get((name, ds))
            why = staleness(rec, cfg, ds, manifests, settings, today,
                            cached if changes is not None else None) if enabled else []
            dss.append({"dataset": ds, "last": _summary(rec), "stale": bool(why), "reasons": why})
        if enabled:
            state = "stale" if (not dss or any(d["stale"] for d in dss)) else "current"
        else:
            state = "gap" if cfg.get("blocked_by") else "off"
        row = {"pair": name, "algorithm": (manifests.get(cfg.get("candidate")) or {}).get("algorithm"),
               "reference": cfg.get("reference"), "candidate": cfg.get("candidate"),
               "enabled": enabled, "state": state, "datasets": dss}
        if cfg.get("blocked_by"):
            row["blocked_by"] = cfg["blocked_by"]
        if cfg.get("note"):
            row["note"] = cfg["note"]
        if state == "stale":
            row["refresh"] = refresh_command([name])
        rows.append(row)
    return rows


def _summary(rec: "dict | None") -> "dict | None":
    if not rec:
        return None
    final = (rec.get("metrics") or {}).get("chimap") or next(iter((rec.get("metrics") or {}).values()),
                                                             {})
    return {"date": rec.get("date"), "result": rec.get("result"), "run_url": rec.get("run_url"),
            "qsmrs": rec.get("qsmrs"), "nrmse": final.get("nrmse"),
            "correlation": final.get("correlation"), "dice": final.get("dice")}


STATE_LABEL = {"current": "✅ current", "stale": "⚠️ stale", "gap": "🚧 gap", "off": "— not enabled"}


def render_status(rows: list, settings: dict, today: str) -> str:
    """parity/STATUS.md: the table docs/parity.md links to, regenerated by the parity workflows."""
    n = settings.get("stale_after_days", 90)
    lines = ["# Port parity status", "",
             f"Generated {today} by `scripts/parity.py status` from `parity/results.json` and "
             "`parity/thresholds.yml`; do not edit by hand. How checks run, and what makes one "
             "stale: [docs/parity.md](../docs/parity.md).", "",
             "A check is **stale** when the reference image changed, QSM.rs `main` changed the "
             f"pair's source files, the pair's limits changed, it is more than {n} days old, or it "
             "failed. A **gap** is a pair whose port does not match its original yet: it is not "
             "enabled, and has no limits that would pass it.", "",
             "| Pair | Original → port | Dataset | Last check | QSM.rs | Result | NRMSE | Status |",
             "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        dss = r["datasets"] or [{"dataset": "—", "last": None, "stale": r["enabled"],
                                 "reasons": ["no dataset configured"] if r["enabled"] else []}]
        for i, d in enumerate(dss):
            last = d["last"] or {}
            when = (f"[{last['date'][:10]}]({last['run_url']})" if last.get("run_url")
                    else (last.get("date") or "")[:10]) if last else "never"
            res = {"pass": "✅ pass", "fail": "❌ fail", "error": "❌ error"}.get(last.get("result"),
                                                                              "—")
            if r["state"] in ("current", "stale"):
                status = "⚠️ stale: " + "; ".join(d["reasons"]) if d["stale"] else "✅ current"
            elif r["state"] == "gap":
                status = f"🚧 gap ({r['blocked_by']})"
            else:
                status = STATE_LABEL["off"] + (f" ({r['note']})" if r.get("note") else "")
            pair = f"`{r['pair']}`" if i == 0 else ""
            sides = f"`{r['reference']}` → `{r['candidate']}`" if i == 0 else ""
            qsmrs = _qsmrs_label({"qsmrs": last.get("qsmrs")}) if last else "—"
            nrmse = _fmt(last.get("nrmse"), "nrmse") if last.get("nrmse") is not None else "—"
            lines.append(f"| {pair} | {sides} | {d['dataset']} | {when} | {qsmrs} | {res} "
                         f"| {nrmse} | {status} |")
    stale = [r["pair"] for r in rows if r["state"] == "stale"]
    if stale:
        lines += ["", "Refresh every stale pair against QSM.rs `main`:", "", "```bash",
                  refresh_command(stale), "```"]
    return "\n".join(lines) + "\n"


ISSUE_TITLE = "Port parity: stale checks"


def render_issue(rows: list, settings: dict, today: str) -> str:
    """The tracking issue's body; empty when nothing is stale (the workflow then closes it)."""
    stale = [r for r in rows if r["state"] == "stale"]
    if not stale:
        return ""
    lines = [f"<!-- parity-status: kept up to date by .github/workflows/parity-status.yml; edits "
             f"are overwritten -->",
             f"**Owner: QSM-CI.** As of {today}, {len(stale)} enabled parity "
             f"pair{'s are' if len(stale) != 1 else ' is'} stale (rules: docs/parity.md, "
             f"\"Staleness\"; full table: [parity/STATUS.md](../blob/main/parity/STATUS.md)).", ""]
    for r in stale:
        lines.append(f"- **`{r['pair']}`** (`{r['reference']}` → `{r['candidate']}`)")
        for d in r["datasets"]:
            if d["stale"]:
                lines.append(f"  - {d['dataset']}: " + "; ".join(d["reasons"]))
        lines.append(f"  - refresh: `{r['refresh']}`")
    lines += ["", "Refresh them all against QSM.rs `main` (a run from `main` records its result, "
              "and this issue closes when nothing is stale):", "", "```bash",
              refresh_command([r["pair"] for r in stale]), "```"]
    return "\n".join(lines) + "\n"


def render_run_summary(records: list, enabled: list, baseline: bool = False) -> str:
    """The run's summary (the workflow's report job): one row per pair × dataset, then the release
    gate's answer — which pairs passed against exactly the QSM.rs commit under test."""
    lines = ["## Parity run summary", ""]
    commits = sorted({(r.get("qsmrs") or {}).get("commit") or "?" for r in records})
    lines += ["| Pair | Dataset | Result | QSM.rs | QSMxT | NRMSE | r |", "|---|---|---|---|---|---|---|"]
    for r in records:
        m = (r.get("metrics") or {}).get("chimap") or {}
        res = {"pass": "✅ pass", "fail": "❌ fail", "error": "❌ no result",
               "baseline": "📏 baseline"}.get(r.get("result"), r.get("result"))
        qx = r.get("qsmxt") or {}
        lines.append(f"| `{r['pair']}` | {r['dataset']} | {res} | {_qsmrs_label(r)} "
                     f"| {('`' + _short(qx.get('commit')) + '`') if qx.get('commit') else (r.get('candidate') or {}).get('qsmxt') or '—'} "
                     f"| {_fmt(m.get('nrmse'), 'nrmse')} | {_fmt(m.get('correlation'))} |")
    if baseline:
        return "\n".join(lines + ["", "Baseline run: no limits applied, nothing recorded."]) + "\n"
    lines.append("")
    for commit in commits:
        rs = [r for r in records if ((r.get("qsmrs") or {}).get("commit") or "?") == commit]
        ver = next(((r.get("qsmrs") or {}).get("version") for r in rs
                    if (r.get("qsmrs") or {}).get("version")), None)
        ok = sorted({r["pair"] for r in rs} - {r["pair"] for r in rs if r["result"] != "pass"})
        bad = sorted({r["pair"] for r in rs if r["result"] != "pass"})
        head = f"QSM.rs `{commit}`" + (f" (v{ver})" if ver else "")
        lines.append(f"**Against {head}:** passed on every dataset run: "
                     + (", ".join(f"`{p}`" for p in ok) or "none")
                     + (f"; failed or no result: {', '.join(f'`{p}`' for p in bad)}" if bad else "")
                     + ".")
    ran = {r["pair"] for r in records}
    missing = [p for p in enabled if p not in ran]
    if missing:
        lines += ["", "Enabled pairs this run did not check: " + ", ".join(f"`{p}`" for p in missing)
                  + "."]
    gate = (len(commits) == 1 and commits[0] != "?" and not missing
            and all(r["result"] == "pass" for r in records))
    lines += ["", ("**Release gate: passed** — every enabled pair passed on every configured "
                   f"dataset against QSM.rs `{commits[0]}`.") if gate else
              "**Release gate: not passed** by this run (a pair failed, an enabled pair was not "
              "run, or the candidates did not all run one QSM.rs commit)."]
    return "\n".join(lines) + "\n"


def _read_json(p: Path):
    return json.loads(Path(p).read_text()) if p and Path(p).exists() else None


def cmd_report(args) -> int:
    """Turn a run's job outputs into records (+ the run summary)."""
    th = load_thresholds(args.thresholds)
    manifests = _manifests()
    matrix = json.loads(args.matrix) if args.matrix else []
    build = _read_json(args.build) if args.build else None
    run = {"date": args.date, "run_id": args.run_id, "run_url": args.run_url,
           "qsmci_commit": args.qsmci_commit, "qsmrs_ref": args.qsmrs_ref,
           "qsmxt_ref": args.qsmxt_ref}
    found = {}
    for f in Path(args.artifacts).glob("**/parity.json"):
        d = json.loads(f.read_text())
        found[(d.get("algorithm"), d.get("phantom"))] = d
    records = []
    for job in matrix:
        pair, ds = job["algorithm"], job["phantom"]
        records.append(make_record(found.get((pair, ds)), pair=pair, phantom=ds,
                                   cfg=th.get(pair) or {}, manifests=manifests, run=run,
                                   build=build))
    if args.out:
        Path(args.out).write_text(json.dumps(records, indent=2, default=str) + "\n")
    summary = render_run_summary(records, [p for p, c in th.items() if (c or {}).get("enabled")],
                                 baseline=args.baseline)
    print(summary)
    if args.summary:
        Path(args.summary).write_text(summary)
    return 0


def cmd_record(args) -> int:
    records = json.loads(Path(args.records).read_text())
    res = merge_records(load_results(args.results), records)
    Path(args.results).write_text(json.dumps(res, indent=1, default=str) + "\n")
    kept = sum(1 for r in records if r.get("result") != "baseline")
    print(f"recorded {kept} check(s) in {args.results}")
    return 0


def cmd_status(args) -> int:
    from datetime import datetime, timezone
    th = load_thresholds(args.thresholds)
    settings = load_settings(args.thresholds)
    if args.stale_after_days is not None:
        settings["stale_after_days"] = args.stale_after_days
    today = args.today or datetime.now(timezone.utc).date().isoformat()
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    changes = None if args.offline else (
        lambda c: github_compare(settings["qsmrs_repo"], c, settings["qsmrs_branch"], token))
    rows = pair_status(th, load_results(args.results), _manifests(), settings, today, changes)
    doc = {"generated": today, "stale_after_days": settings["stale_after_days"],
           "qsmrs": {"repo": settings["qsmrs_repo"], "branch": settings["qsmrs_branch"],
                     "checked": not args.offline},
           "stale": [r["pair"] for r in rows if r["state"] == "stale"], "pairs": rows}
    if args.json:
        Path(args.json).write_text(json.dumps(doc, indent=1, default=str) + "\n")
    md = render_status(rows, settings, today)
    if args.markdown:
        Path(args.markdown).write_text(md)
    if args.issue:
        Path(args.issue).write_text(render_issue(rows, settings, today))
    if not (args.json or args.markdown or args.issue):
        print(md)
    else:
        print(f"stale: {', '.join(doc['stale']) or 'none'}")
    return 0


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
    p.add_argument("--algorithm", default="enabled",
                   help="pairs, comma-separated, and/or 'enabled' / 'all-configured'")
    p.add_argument("--dataset", default="configured",
                   help="datasets.json keys, comma-separated, or 'configured'")
    p.set_defaults(fn=cmd_pairs)
    p = sub.add_parser("report", help="a run's job results → records + the run summary")
    p.add_argument("--artifacts", type=Path, required=True,
                   help="directory holding the jobs' parity.json files (any depth)")
    p.add_argument("--matrix", required=True, help="the run's job matrix (JSON)")
    p.add_argument("--build", type=Path, help="built.json from the qsmxt job, if it ran")
    for k in ("date", "run-id", "run-url", "qsmci-commit", "qsmrs-ref", "qsmxt-ref"):
        p.add_argument(f"--{k}", default="")
    p.add_argument("--baseline", action="store_true")
    p.add_argument("--out", type=Path, help="write the records (JSON list) here")
    p.add_argument("--summary", type=Path, help="write the run summary (markdown) here")
    p.set_defaults(fn=cmd_report)
    p = sub.add_parser("record", help="append a run's records to parity/results.json")
    p.add_argument("--records", type=Path, required=True)
    p.add_argument("--results", type=Path, default=RESULTS)
    p.set_defaults(fn=cmd_record)
    p = sub.add_parser("status", help="last check and staleness per pair")
    p.add_argument("--results", type=Path, default=RESULTS)
    p.add_argument("--json", type=Path, help="e.g. parity/status.json")
    p.add_argument("--markdown", type=Path, help="e.g. parity/STATUS.md")
    p.add_argument("--issue", type=Path, help="the tracking issue's body (empty: nothing stale)")
    p.add_argument("--stale-after-days", type=int, help="default: thresholds.yml stale_after_days")
    p.add_argument("--today", help="YYYY-MM-DD (default: today, UTC)")
    p.add_argument("--offline", action="store_true",
                   help="skip rule (b): do not ask GitHub what changed in QSM.rs")
    p.set_defaults(fn=cmd_status)
    for name, fn in (("run", cmd_run), ("compare", cmd_compare)):
        p = sub.add_parser(name)
        p.add_argument("--algorithm", required=True)
        p.add_argument("--phantom", default="sim", help="scripts/datasets.json key (thresholds key)")
        p.add_argument("--dataset", required=True, type=Path, help="dataset dir (inputs/, groundtruth/)")
        p.add_argument("--work", required=True, type=Path)
        p.set_defaults(fn=fn)
        if name == "run":
            p.add_argument("--runner", default="docker", choices=["docker", "podman", "apptainer", "local"])
            p.add_argument("--qsmrs-image", metavar="REF",
                           help="run every QSM.rs step (source: qsmrs) in this image instead of "
                                "the one its algorithm.yml pins (e.g. a qsmxt built from a ref)")
        else:
            p.add_argument("--mask", type=Path, help="default: <dataset>/inputs/mask.nii.gz")
            p.add_argument("--baseline", action="store_true",
                           help="measure and suggest limits; never fail on them")
            p.add_argument("--note", default="", help="a line for the report, e.g. which QSM.rs "
                                                          "build the candidate ran")
            p.add_argument("--report", type=Path)
            p.add_argument("--json", type=Path)
    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
