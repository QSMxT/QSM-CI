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
  status   say, per pair and track, when it was last checked, against which QSMxT and QSM.rs,
           with what result, and whether that check still stands (`staleness`,
           `released_staleness`); writes parity/status.json, the tables in parity/STATUS.md, the
           tracking issue's body and (--badges) the shields.io endpoint files.
  badges   write those badge files from an existing parity/status.json (the site deploy).

Two tracks (docs/parity.md, "Tracks"): `released` checks the latest QSMxT release (its shipped
binary, with the QSM.rs it pins) and keeps every release's result; `dev` checks QSMxT main with
qsm-core at QSM.rs main (the QSM.rs release gate). Two more subcommands serve the released track:

  unavailable    write the job's result as "not in <release>" when the release has no such
                 command or option (before the run, or from a failed run's log).
  released-plan  what parity-release.yml dispatches: a new release, or pairs whose reference or
                 settings changed since their run against it.

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
# A floor under the |Δ| limits (ppm): a pair that agrees bit for bit today (TKD, Tikhonov on the
# simulation) would otherwise get a limit of 0, which float noise from a different FFT plan or
# thread split would fail. 1e-6 ppm is far below anything a real change produces.
ABS_FLOOR = 1e-6


# ---------------------------------------------------------------------------------------------------
# Pairs
# ---------------------------------------------------------------------------------------------------

def load_thresholds(path: Path = THRESHOLDS) -> dict:
    doc = yaml.safe_load(Path(path).read_text()) or {}
    return doc.get("pairs") or {}


def load_settings(path: Path = THRESHOLDS) -> dict:
    """thresholds.yml's top-level settings (everything but `pairs`), with defaults."""
    doc = yaml.safe_load(Path(path).read_text()) or {}
    out = dict(DEFAULT_SETTINGS)
    out.update({k: v for k, v in doc.items() if k not in ("pairs", "no_original")})
    return out


def load_no_original(path: Path = THRESHOLDS) -> dict:
    """thresholds.yml's `no_original`: {name: {"covers", "note"}} for QSM.rs methods that have no
    original code to check against (QSMxT/QSM-CI#302). They get a row and a badge, never a pair."""
    doc = yaml.safe_load(Path(path).read_text()) or {}
    return {k: (v or {}) for k, v in (doc.get("no_original") or {}).items()}


# thresholds.yml's top-level settings. The `*_shared_paths` apply to every pair on top of its own
# `qsmrs_paths` / `qsmxt_paths` (rules b and f).
DEFAULT_SETTINGS = {"qsmrs_repo": "astewartau/QSM.rs", "qsmrs_branch": "main",
                    "qsmrs_shared_paths": ["Cargo.lock"],
                    "qsmxt_repo": "QSMxT/QSMxT", "qsmxt_branch": "main",
                    "qsmxt_shared_paths": ["Cargo.lock"],
                    "site_url": "https://qsmxt.github.io/QSM-CI"}


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
    out["max_abs_max"] = _round_up(max(metrics["max_abs"] * (1 + ABS_REL), ABS_FLOOR))
    out["p99_abs_max"] = _round_up(max(metrics["p99_abs"] * (1 + ABS_REL), ABS_FLOOR))
    return out


def evaluate(results: dict, ds_cfg: dict, final: "str | list",
             intermediates_only: bool = False) -> dict:
    """Apply the dataset's limits to every compared map. `results` is {name: metrics} with the final
    artifact under its artifact name (e.g. "chimap") and intermediates under theirs. The final
    artifact's limits are ds_cfg[final]; an intermediate's are ds_cfg["intermediates"][name].

    Returns {name: {"metrics", "checks", "status"}} with status "pass", "fail" or "info" (compared
    but no limits configured — reported, never fails), plus "ok": no "fail" anywhere and the final
    artifact has limits. A final artifact without limits is "fail": an enabled pair must say what
    agreement it expects. A stage with several outputs (χ-separation's chi-para and chi-dia) passes
    them all as `final`: each is a final artifact with its own limits.

    `intermediates_only` (the pair's `intermediates_only: true`): the final artifact is not like
    for like (the port reaches it by another route, e.g. another unwrapper), so it is reported
    without limits, and the pair needs limits on at least one intermediate instead."""
    finals = [final] if isinstance(final, str) else list(final)
    inter = (ds_cfg or {}).get("intermediates") or {}
    out = {}
    for name, metrics in results.items():
        limits = (ds_cfg or {}).get(name) if name in finals else inter.get(name)
        rows = check(metrics, limits)
        if intermediates_only and name in finals:
            status = "info"
        elif not limits and name in finals:
            status = "fail"
        elif not limits:
            status = "fail" if any(not r["ok"] for r in rows) else "info"
        else:
            status = "pass" if all(r["ok"] for r in rows) else "fail"
        out[name] = {"metrics": metrics, "checks": rows, "status": status,
                     "limits": limits or {}}
    ok = bool(out) and all(v["status"] != "fail" for v in out.values())
    if intermediates_only:   # something with limits must have been compared
        ok = ok and any(v["limits"] for n, v in out.items() if n not in finals)
    return {"maps": out, "ok": ok}


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
                  baseline: bool, unmatched: dict, provenance: dict, note: str = "",
                  intermediates_only: bool = False) -> str:
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
    finals = provenance.get("finals") or [provenance.get("final")]
    if intermediates_only:
        lines += ["", "Intermediates-only pair: the final map (" + ", ".join(f"`{f}`" for f in finals)
                  + ") is reported but not compared against limits; the intermediates are."]
        if not baseline and not any(v["limits"] for n, v in maps.items() if n not in finals):
            lines.append(f"❌ No intermediate with limits in parity/thresholds.yml for `{phantom}` "
                         "was compared.")
    if unmatched.get("reference") or unmatched.get("candidate"):
        lines += ["", "Intermediates written by one side only (not compared): "
                  + "; ".join(f"{s}: {', '.join(f'`{n}`' for n in ns)}"
                              for s, ns in unmatched.items() if ns)]
    if baseline:
        sugg = {"datasets": {phantom: {}}}
        ds = sugg["datasets"][phantom]
        for name, v in maps.items():
            lim = derive_limits(v["metrics"])
            if name in finals:
                if not intermediates_only:
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
    """The QSM.rs a qsmxt binary was built with, from its `--version` output: a release says
    `QSM.rs (qsm-core): v0.39.0 (42ab6201…)`, a build from a git pin `QSM.rs (qsm-core):
    rev-da928e0c…`. Returns {"qsmrs_version" (None for a rev), "qsmrs_commit"}, or {}."""
    import re
    m = re.search(r"qsm-core\)?:\s*v?([0-9][^\s(]*)\s*\(([0-9a-f]{7,40})\)", text or "")
    if m:
        return {"qsmrs_version": m.group(1), "qsmrs_commit": m.group(2)}
    m = re.search(r"qsm-core\)?:\s*rev-([0-9a-f]{7,40})", text or "")
    return {"qsmrs_version": None, "qsmrs_commit": m.group(1)} if m else {}


def apply_names(inter: Path, names: "dict | None", mask_path: "Path | None" = None) -> None:
    """Rename a side's intermediates to the names they are compared under (CONTRACT.md,
    "Intermediates"), for a method whose own names differ — e.g. a compiled MATLAB image that
    predates the convention. `names` is {native: canonical} or {native: {name: canonical,
    complement: true}}; `complement` turns a mask into its complement inside the dataset mask (the
    original's `vasc_only` is tissue without vessels; `vessel_mask` is the vessels). `clip_min: x`
    sets values below x to x, for a deviation the port documents (QSM.rs clamps R2* at 0 where
    MEDI's arlo.m returns negative noise estimates), so the rest is still compared exactly. The
    canonical name may equal the native one."""
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
        elif spec.get("clip_min") is not None:
            import nibabel as nib
            import numpy as np
            img = nib.load(str(src))
            out = np.maximum(np.asanyarray(img.dataobj), float(spec["clip_min"]))
            hdr = img.header.copy()
            hdr.set_data_dtype(out.dtype)
            hdr.set_slope_inter(1, 0)   # the data are written as they are (no rescaling)
            if src != dst:
                src.unlink()
            nib.save(nib.Nifti1Image(out, img.affine, hdr), str(dst))
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
        pipeline.prepare_input(algo["consumes"], sources, idir, algo.get("optional", ()))
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
    finals = list(algo["produces"])   # every output of the last step (χ-separation has two)
    for art in finals:
        shutil.copy(sources[art], out / ARTIFACT_FILE[art])
    apply_names(inter, names, Path(dataset) / "inputs" / "mask.nii.gz")
    prov = {"chain": chain, "steps": steps, "image": steps[-1]["image"], "runtime_s": t_all,
            "final": final, "finals": finals}
    (out / "provenance.json").write_text(json.dumps(prov, indent=2) + "\n")
    return prov


def optional_feeds(cfg: dict, phantom: str, manifests: "dict | None" = None) -> list:
    """The pair's feeds on a dataset that the candidate's first step takes as an `optional_inputs:`
    artifact (QSMART's `reliability`): the port runs without them, only on a different input."""
    manifests = _manifests() if manifests is None else manifests
    feed = ((cfg.get("datasets") or {}).get(phantom) or {}).get("feed") or {}
    first = side_chain(cfg, "candidate", phantom)[0]
    optional = set((manifests.get(first) or {}).get("optional_inputs") or [])
    return sorted(a for a in feed if a in optional)


DROPPED = "dropped_feeds.json"   # in the candidate's work dir: feeds a release run went without
DROPPED_SETTINGS = "dropped_settings.json"   # … and `candidate_set` settings it went without


def rejected_setting(cfg: dict, phantom: str, log: str) -> "str | None":
    """The pair's `candidate_set` key behind qsmxt's refusal in a run log (clap's `unexpected
    argument '--qsmart-offset-grid'` or `invalid value 'qsmjl' for '--variant <V>'`): the key whose
    hyphenated name the refused option contains (offset_grid → --qsmart-offset-grid), the longest if
    several do; None when no setting matches (the refusal is about the port itself)."""
    import re
    hit = clap_rejection(log)
    if not hit or hit.startswith("required argument"):   # a missing input: no setting to drop
        return None
    m = re.search(r"'(--[A-Za-z0-9-]+)", hit[hit.find(" for ") :] if " for " in hit else hit)
    if not m:
        return None
    flag = m.group(1).lstrip("-").lower()
    keys = [k for k in side_set(cfg, "candidate", phantom)
            if str(k).replace("_", "-").lower() in flag]
    return max(keys, key=len) if keys else None


def cmd_run(args) -> int:
    """Run the reference, then the candidate. `--candidate-only --drop-optional-feeds` reruns just
    the candidate without the pair's optional feeds (released track: the release's qsmxt has no
    option for one, e.g. qsmxt v10.0.0 and `qsmart --reliability`); it exits 3 when there is no
    optional feed to drop or no reference output to rerun against."""
    import shutil
    th = load_thresholds(args.thresholds)
    cfg = pair_config(th, args.algorithm)
    ds_cfg = (cfg.get("datasets") or {}).get(args.phantom) or {}
    work = Path(args.work)
    drop_asked = getattr(args, "drop_optional_feeds", False)
    drop = optional_feeds(cfg, args.phantom) if drop_asked else []
    unset = [k for k in (getattr(args, "drop_setting", None) or [])
             if k in side_set(cfg, "candidate", args.phantom)]
    if (drop_asked or getattr(args, "drop_setting", None)) and not (drop or unset):
        print(f"{args.algorithm}: no optional feed or candidate setting to run without")
        return 3
    if getattr(args, "candidate_only", False):
        if not (work / "reference" / "provenance.json").exists():
            print(f"{args.algorithm}: no reference output in {work} to rerun the candidate against")
            return 3
    else:
        run_side(side_chain(cfg, "reference", args.phantom), Path(args.dataset), work / "reference",
                 args.runner, qsmrs_image=args.qsmrs_image or None,
                 names=cfg.get("reference_names"), overrides=side_set(cfg, "reference", args.phantom))
    # `feed: {totalfield: totalfield}` hands the candidate the reference's intermediate of that name
    # (after reference_names) in place of the dataset's artifact, so both reconstruct from the same
    # input. A declared feed whose intermediate the reference did not write is an error, never a
    # silent fallback; dropping an optional feed is asked for explicitly and recorded.
    feed = {}
    for art, name in (ds_cfg.get("feed") or {}).items():
        if art in drop:
            continue
        f = work / "reference" / "intermediates" / f"{name}.nii.gz"
        if not f.exists():
            raise SystemExit(f"feed: {art} <- reference intermediate '{name}', which "
                             f"{cfg['reference']} did not write")
        feed[art] = f
    if (work / "candidate").exists():
        shutil.rmtree(work / "candidate")
    run_side(side_chain(cfg, "candidate", args.phantom), Path(args.dataset), work / "candidate",
             args.runner, feed=feed, qsmrs_image=args.qsmrs_image or None,
             names=cfg.get("candidate_names"),
             overrides={k: v for k, v in side_set(cfg, "candidate", args.phantom).items()
                        if k not in unset})
    if drop:
        (work / "candidate" / DROPPED).write_text(json.dumps(drop) + "\n")
        print(f"{args.algorithm}: the candidate ran without the optional feed(s) {', '.join(drop)}")
    if unset:
        (work / "candidate" / DROPPED_SETTINGS).write_text(json.dumps(unset) + "\n")
        print(f"{args.algorithm}: the candidate ran without the setting(s) {', '.join(unset)}")
    return 0


def _load(path: Path):
    import nibabel as nib
    import numpy as np
    return np.asanyarray(nib.load(str(path)).dataobj)


def compare_dirs(ref_dir: Path, cand_dir: Path, mask_path: Path,
                 final: "str | list") -> "tuple[dict, dict]":
    """({name: metrics}, unmatched) for the final artifact(s) and the intermediates both sides
    wrote."""
    finals = [final] if isinstance(final, str) else list(final)
    from qsm_ci.stages import ARTIFACT_FILE
    mask = _load(mask_path)
    results = {f: compare_maps(_load(ref_dir / ARTIFACT_FILE[f]), _load(cand_dir / ARTIFACT_FILE[f]),
                               mask) for f in finals}
    names = {s: {p.name[:-7] for p in (d / "intermediates").glob("*.nii.gz")}
             for s, d in (("reference", ref_dir), ("candidate", cand_dir))}
    for s in names.values():
        s.difference_update(finals)   # a copy of a final map (QSMART's recon writes one) is not a step
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
    final = prov["reference"].get("finals") or prov["reference"].get("final") or "chimap"
    def _dropped(name):
        f = work / "candidate" / name
        return json.loads(f.read_text()) if f.exists() else []
    dropped, unset = _dropped(DROPPED), _dropped(DROPPED_SETTINGS)
    note = args.note + (f" Run without the optional feed(s) {', '.join(dropped)}: this qsmxt has no "
                        f"option for them." if dropped else "") \
        + (f" Run without the candidate setting(s) {', '.join(unset)}: this qsmxt has no option "
           f"for them." if unset else "")
    mask = Path(args.mask) if args.mask else Path(args.dataset) / "inputs" / "mask.nii.gz"
    results, unmatched = compare_dirs(work / "reference", work / "candidate", mask, final)
    verdict = evaluate(results, ds_cfg, final, bool(cfg.get("intermediates_only")))
    report = render_report(algorithm=args.algorithm, phantom=args.phantom,
                           reference=cfg["reference"], candidate=cfg["candidate"], verdict=verdict,
                           baseline=args.baseline, unmatched=unmatched,
                           provenance={**prov, "final": final if isinstance(final, str) else final[0],
                                       "finals": [final] if isinstance(final, str) else final},
                           note=note.strip(),
                           intermediates_only=bool(cfg.get("intermediates_only")))
    print(report)
    if args.report:
        Path(args.report).write_text(report)
    if args.json:
        Path(args.json).write_text(json.dumps({
            "algorithm": args.algorithm, "phantom": args.phantom, "reference": cfg["reference"],
            "candidate": cfg["candidate"], "baseline": args.baseline, "provenance": prov,
            "note": note.strip(), **({"dropped_feeds": dropped} if dropped else {}),
            **({"dropped_settings": unset} if unset else {}),
            "unmatched": unmatched, **verdict,
            "suggested": {n: derive_limits(v["metrics"]) for n, v in verdict["maps"].items()},
        }, indent=2, default=str) + "\n")
    return 0 if (args.baseline or verdict["ok"]) else 1


# ---------------------------------------------------------------------------------------------------
# Tracks. Every record belongs to one of two tracks (docs/parity.md, "Tracks"):
#   released  a QSMxT release (the binary it ships, with the QSM.rs it pins) against each original.
#             A release never changes, so it is rerun only for a new release or a changed reference
#             or pair settings. Every release's records are kept: the history the site shows.
#   dev       QSMxT main built with qsm-core moved to QSM.rs main (or a release candidate): the QSM.rs
#             release gate. Stale on any change to the pair's paths; 50 newest records kept.
# ---------------------------------------------------------------------------------------------------

RELEASED, DEV = "released", "dev"
TRACKS = (RELEASED, DEV)


def record_track(rec: dict) -> str:
    """A record's track. Records from before the tracks existed were all QSM.rs main × QSMxT main
    builds (parity/results.json was migrated to say so), so a record without one is `dev`."""
    return rec.get("track") or DEV


def release_key(tag: "str | None") -> tuple:
    """Sort key for a release tag: v10.0.0 < v10.0.1 < v10.1.0; a pre-release before its release."""
    import re
    m = re.match(r"v?(\d+)(?:\.(\d+))?(?:\.(\d+))?(.*)", tag or "")
    if not m:
        return (-1, -1, -1, 0, tag or "")
    return (int(m.group(1)), int(m.group(2) or 0), int(m.group(3) or 0), 0 if m.group(4) else 1,
            m.group(4))


# ---------------------------------------------------------------------------------------------------
# Run history (parity/results.json) and staleness (parity/status.json, parity/STATUS.md)
# ---------------------------------------------------------------------------------------------------

RESULTS = ROOT / "parity" / "results.json"
HISTORY_PER_CHECK = 50   # dev-track records kept per pair × dataset in results.json
REPO = "QSMxT/QSM-CI"

# The pair settings that decide what a check measures and how it is judged. A change to any of them
# (or to the dataset's entry, limits included) makes the last check stale (rule c). `measured`,
# `enabled`, `blocked_by`, `qsmrs_paths` and `qsmxt_paths` are bookkeeping and do not count.
MEASURED_BY = ("reference", "candidate", "reference_names", "candidate_names", "reference_set",
               "candidate_set", "intermediates_only")


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
    counts as a failed check; `{"unavailable": why}` when the QSMxT release under test has no such
    command or option, `parity.py unavailable`). `run` holds the run's date, id, URL, QSM-CI
    commit, track and release, and the qsmrs_ref / qsmxt_ref it was dispatched with; `build` is the
    qsmxt job's built.json. The QSM.rs commit is what the candidate's own qsmxt reports
    (`qsmxt --version`), so a release is recorded as exactly as a build."""
    ref_slug, cand_slug = cfg.get("reference"), cfg.get("candidate")
    ref_image = (manifests.get(ref_slug) or {}).get("image")
    build = build or {}
    rec = {"pair": pair, "dataset": phantom, "track": run.get("track") or DEV,
           **({"release": run["release"]} if run.get("release") else {}),
           "date": run.get("date"), "run_id": run.get("run_id"), "run_url": run.get("run_url"),
           "qsmci_commit": run.get("qsmci_commit"),
           "thresholds": thresholds_version(cfg, phantom),
           "reference": {"slug": ref_slug, "image": ref_image, "digest": image_digest(ref_image)},
           "candidate": {"slug": cand_slug},
           "qsmrs": {"ref": run.get("qsmrs_ref") or None, "commit": build.get("qsmrs_commit"),
                     # a git build's Cargo version is a placeholder (0.0.0 on QSM.rs main)
                     "version": build.get("qsmrs_version")
                     if build.get("qsmrs_version") not in (None, "", "0.0.0") else None},
           "qsmxt": {"ref": build.get("qsmxt_ref") or run.get("qsmxt_ref") or run.get("release")
                     or None, "commit": build.get("qsmxt_commit")}}
    if res is None:
        rec["result"] = "error"
        rec["failed"] = ["no comparison: the job failed or was cancelled before `compare` ran"]
        return rec
    prov = res.get("provenance") or {}
    cst = ((prov.get("candidate") or {}).get("steps") or [{}])[-1]
    rst = ((prov.get("reference") or {}).get("steps") or [{}])[-1]
    rec["candidate"].update({k: v for k, v in (
        ("image", cst.get("image")), ("digest", image_digest(cst.get("image")) or cst.get("id")),
        ("qsmxt", cst.get("qsmxt"))) if v or not res.get("unavailable")})
    if rst.get("id"):
        rec["reference"]["id"] = rst["id"]
    if cst.get("qsmrs_commit"):
        rec["qsmrs"]["commit"] = cst["qsmrs_commit"]
        if cst.get("qsmrs_version"):
            rec["qsmrs"]["version"] = cst["qsmrs_version"]
    if res.get("unavailable"):
        rec["result"] = "unavailable"
        rec["failed"] = [str(res["unavailable"])]
        return rec
    for k in ("dropped_feeds", "dropped_settings"):
        if res.get(k):
            rec[k] = list(res[k])
    if cst.get("set") or rst.get("set"):
        rec["set"] = {k: v for k, v in (("reference", rst.get("set")),
                                        ("candidate", cst.get("set"))) if v}
    maps = res.get("maps") or {}
    if cfg.get("intermediates_only"):   # what is compared first (the run summary shows the first map)
        maps = dict(sorted(maps.items(), key=lambda kv: not kv[1].get("limits")))
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
    return {"schema": 2, "checks": list(doc.get("checks") or [])}


def merge_records(results: dict, records: list, keep: int = HISTORY_PER_CHECK) -> dict:
    """results.json with `records` added: a record replaces one from the same run, pair and
    dataset (re-recording a run is a no-op), and baselines are left out (they apply no limits).
    Retention differs by track: each dev pair × dataset keeps its `keep` newest records; the
    released track keeps one record per pair × dataset × release (the newest: a rerun for a changed
    reference replaces the release's earlier result), for every release."""
    key = lambda r: (record_track(r), r.get("run_id"), r.get("pair"), r.get("dataset"))  # noqa: E731
    new = [{**r, "track": record_track(r)} for r in records if r.get("result") != "baseline"]
    seen = {key(r) for r in new}
    checks = [r for r in results.get("checks") or [] if key(r) not in seen] + new
    checks.sort(key=lambda r: (r.get("pair") or "", r.get("dataset") or "", r.get("date") or ""))
    out, count = [], {}
    for r in reversed(checks):
        if record_track(r) == RELEASED:
            k, limit = (RELEASED, r.get("pair"), r.get("dataset"), r.get("release")), 1
        else:
            k, limit = (DEV, r.get("pair"), r.get("dataset")), keep
        count[k] = count.get(k, 0) + 1
        if count[k] <= limit:
            out.append(r)
    return {"schema": 2, "checks": list(reversed(out))}


def latest_records(results: dict, track: str = DEV, release: "str | None" = None) -> dict:
    """{(pair, dataset): newest record} of one track (and, for the released track, one release)."""
    out = {}
    for r in results.get("checks") or []:
        if record_track(r) != track or (release is not None and r.get("release") != release):
            continue
        k = (r.get("pair"), r.get("dataset"))
        if k not in out or (r.get("date") or "") >= (out[k].get("date") or ""):
            out[k] = r
    return out


def recorded_releases(results: dict) -> list:
    """The QSMxT releases the released track has records for, newest first."""
    tags = {r.get("release") for r in results.get("checks") or []
            if record_track(r) == RELEASED and r.get("release")}
    return sorted(tags, key=release_key, reverse=True)


def _short(sha: "str | None", n: int = 7) -> str:
    return (sha or "")[:n] or "?"


def _qsmrs_label(rec: "dict | None") -> str:
    q = (rec or {}).get("qsmrs") or {}
    if not q.get("commit"):
        return "unknown"
    return (f"v{q['version']} " if q.get("version") else "") + f"`{_short(q['commit'])}`"


def refresh_command(pairs: list, track: str = DEV, release: "str | None" = None,
                    qsmrs_ref: str = "main") -> str:
    """The dispatch that refreshes `pairs` on a track: the latest release, or QSM.rs main."""
    what = f"-f qsmxt_release={release}" if track == RELEASED else f"-f qsmrs_ref={qsmrs_ref}"
    return (f"gh workflow run parity.yml -R {REPO} -f algorithm={','.join(pairs)} "
            f"-f dataset=configured {what}")


def _gh_get(url: str, token: "str | None" = None):
    """GET a GitHub API URL: (json, None) or (None, (HTTP code or None, message))."""
    import urllib.error
    import urllib.request
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json",
                                               **({"Authorization": f"Bearer {token}"}
                                                  if token else {})})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r), None
    except urllib.error.HTTPError as e:
        return None, (e.code, f"HTTP {e.code}")
    except (urllib.error.URLError, TimeoutError) as e:
        return None, (None, str(e))


def github_compare(repo: str, base: str, head: str, token: "str | None" = None) -> dict:
    """The files changed on `head` since `base` (GitHub's compare API, from their merge base):
    {"ahead_by", "files"} or {"error"}. The API lists at most 300 files; `truncated` says so."""
    doc, err = _gh_get(f"https://api.github.com/repos/{repo}/compare/{base}...{head}?per_page=100",
                       token)
    if err:
        return {"error": f"compare {_short(base)}...{head}: {err[1]}", "unknown_commit": err[0] == 404}
    files = set()
    for f in doc.get("files") or []:
        files.add(f.get("filename"))
        if f.get("previous_filename"):
            files.add(f["previous_filename"])
    return {"ahead_by": doc.get("ahead_by", 0), "files": sorted(x for x in files if x),
            "truncated": len(doc.get("files") or []) >= 300}


def github_latest_release(repo: str, token: "str | None" = None) -> "str | None":
    """The tag of `repo`'s latest release (GitHub's "Latest": not a draft or a pre-release)."""
    doc, err = _gh_get(f"https://api.github.com/repos/{repo}/releases/latest", token)
    return None if err else (doc or {}).get("tag_name")


def touched(files: list, paths: list) -> list:
    """The files under any of `paths` (a file, or a directory prefix)."""
    ps = [p.rstrip("/") for p in paths or []]
    return [f for f in files if any(f == p or f.startswith(p + "/") for p in ps)]


def _changed(changes, commit: "str | None", paths: list, repo: str, branch: str, what: str) -> list:
    """The staleness reason for one repository's rule (b or f): [] when nothing under `paths`
    changed on `branch` since `commit`. A network error is not a verdict (no reason)."""
    if not paths:
        return []
    if not commit:
        return [f"the {what} commit of the last check is not recorded"]
    c = changes(commit) or {}
    if c.get("error"):
        return ([f"the checked {what} commit {_short(commit)} is not in {repo}"]
                if c.get("unknown_commit") else [])
    hit = touched(c.get("files") or [], paths)
    if not hit:
        return []
    shown = ", ".join(f"`{f}`" for f in hit[:4]) + (" …" if len(hit) > 4 else "")
    return [f"{what} {branch} changed {shown} since the checked {_short(commit)} "
            f"({c.get('ahead_by', '?')} commits)"]


def qsmxt_commit(rec: dict) -> "str | None":
    """The QSMxT commit a check ran: the build's, else the release tag of the pinned image's
    `qsmxt --version` (e.g. "qsmxt 10.0.0" → v10.0.0), else None."""
    import re
    c = (rec.get("qsmxt") or {}).get("commit")
    if c:
        return c
    m = re.search(r"\b(\d+\.\d+\.\d+)\b", str((rec.get("candidate") or {}).get("qsmxt") or ""))
    return f"v{m.group(1)}" if m else None


def _reference_changed(rec: dict, cfg: dict, manifests: dict) -> list:
    ref_now = image_digest((manifests.get(cfg.get("reference")) or {}).get("image"))
    ref_then = ((rec.get("reference") or {}).get("digest"))
    if ref_now != ref_then:
        return [f"reference image changed: checked {_short(ref_then, 19)}, algorithm.yml "
                f"pins {_short(ref_now, 19)}"]
    return []


def staleness(rec: "dict | None", cfg: dict, phantom: str, manifests: dict, settings: dict,
              changes=None, qsmxt_changes=None) -> list:
    """Why the last dev-track check of a pair on a dataset no longer stands ([] when it does):

      (a) the reference image pinned in algorithm.yml is not the one last checked;
      (b) QSM.rs `main` has commits touching the pair's `qsmrs_paths`, or `qsmrs_shared_paths`
          (Cargo.lock), since the QSM.rs commit last checked (`changes(commit)` returns
          github_compare's answer; None skips this rule);
      (c) the pair's settings or limits for the dataset changed since (thresholds_version);
      (d) it was never checked;
      (e) the last check failed (or ended without a result);
      (f) QSMxT `main` has commits touching the pair's `qsmxt_paths`, or `qsmxt_shared_paths`
          (Cargo.lock), since the QSMxT commit last checked (`qsmxt_changes`; None skips it).

    There is no age limit: a check stands until one of these changes."""
    if rec is None:
        return ["never checked"]
    why = _reference_changed(rec, cfg, manifests)
    if changes is not None:
        why += _changed(changes, (rec.get("qsmrs") or {}).get("commit"),
                        list(cfg.get("qsmrs_paths") or []) + list(settings.get("qsmrs_shared_paths") or []),
                        settings["qsmrs_repo"], settings["qsmrs_branch"], "QSM.rs")
    if rec.get("thresholds") != thresholds_version(cfg, phantom):
        why.append("the pair's settings or limits for this dataset changed since")
    if rec.get("result") == "error":
        why.append("the last check ended without a result")
    elif rec.get("result") != "pass":
        why.append("the last check failed" + (f": {rec['failed'][0]}" if rec.get("failed") else ""))
    if qsmxt_changes is not None:
        why += _changed(qsmxt_changes, qsmxt_commit(rec),
                        list(cfg.get("qsmxt_paths") or []) + list(settings.get("qsmxt_shared_paths") or []),
                        settings["qsmxt_repo"], settings["qsmxt_branch"], "QSMxT")
    return why


def released_staleness(rec: "dict | None", cfg: dict, phantom: str, manifests: dict,
                       release: "str | None") -> "tuple[list, bool]":
    """(reasons, rerun) for a pair × dataset on the released track. A release never changes, so
    only these flag it: no run against the latest release; the reference image or the pair's
    settings/limits changed since that run (both `rerun`: parity-release.yml reruns them); or that
    run ended without a result (flagged, not rerun by itself: an error that repeats would loop). A
    failure, or a port the release does not have, is the release's result, not staleness."""
    if not release:
        return [], False     # nothing to run against (offline, with no release recorded yet)
    if rec is None:
        return [f"not run against QSMxT {release}"], True
    why = _reference_changed(rec, cfg, manifests)
    if rec.get("thresholds") != thresholds_version(cfg, phantom):
        why.append("the pair's settings or limits for this dataset changed since")
    rerun = bool(why)
    if rec.get("result") == "error":
        why.append(f"the run against {release} ended without a result")
    return why, rerun


def _memo(fn):
    if fn is None:
        return None
    cache: dict = {}

    def get(commit):
        if commit not in cache:
            cache[commit] = fn(commit)
        return cache[commit]
    return get


def anchor(name: str) -> str:
    """The Parity page's row id for a pair (or a no-original entry): `#pair-<name>`."""
    return f"pair-{name}"


def pair_status(thresholds: dict, results: dict, manifests: dict, settings: dict,
                changes=None, qsmxt_changes=None, no_original: "dict | None" = None,
                track: str = DEV, release: "str | None" = None) -> list:
    """One row per configured pair on one track: its state and, per dataset, the last check and why
    it is stale. State: `current` (enabled, every dataset's last check stands), `stale`, `gap`
    (disabled and `blocked_by` a known gap: the port does not match its original yet), `off`
    (disabled: not verified or not measured yet). Then one `no-original` row per `no_original`
    entry. Every row carries its badge (`badge`).

    The dev track applies `staleness` to its newest records; the released track reads the records
    of `release` (the latest QSMxT release) and applies `released_staleness`."""
    last = latest_records(results, track, release if track == RELEASED else None)
    if track == RELEASED and not release:
        last = {}
    changes, qsmxt_changes = _memo(changes), _memo(qsmxt_changes)
    rows = []
    for name, cfg in thresholds.items():
        cfg = cfg or {}
        enabled = bool(cfg.get("enabled"))
        dss = []
        for ds in sorted((cfg.get("datasets") or {}).keys()):
            rec = last.get((name, ds))
            d = {"dataset": ds, "last": _summary(rec, final_maps(cfg, ds))}
            if track == RELEASED:
                why, rerun = released_staleness(rec, cfg, ds, manifests, release) if enabled \
                    else ([], False)
                d["rerun"] = rerun
            else:
                why = staleness(rec, cfg, ds, manifests, settings, changes, qsmxt_changes) \
                    if enabled else []
            d.update(stale=bool(why), reasons=why)
            dss.append(d)
        if enabled:
            state = "stale" if (not dss or any(d["stale"] for d in dss)) else "current"
        else:
            state = "gap" if cfg.get("blocked_by") else "off"
        row = {"pair": name, "algorithm": (manifests.get(cfg.get("candidate")) or {}).get("algorithm"),
               "reference": cfg.get("reference"), "candidate": cfg.get("candidate"),
               "enabled": enabled, "state": state, "anchor": anchor(name), "datasets": dss}
        if cfg.get("blocked_by"):
            row["blocked_by"] = cfg["blocked_by"]
        if cfg.get("note"):
            row["note"] = cfg["note"]
        if state == "stale" and (track == DEV or release):
            row["refresh"] = refresh_command([name], track, release)
        row["badge"] = badge(row, track, release)
        rows.append(row)
    for name, entry in (no_original or {}).items():
        row = {"pair": name, "state": "no-original", "enabled": False, "anchor": anchor(name),
               "covers": entry.get("covers"), "note": entry.get("note"), "datasets": []}
        row["badge"] = badge(row, track, release)
        rows.append(row)
    return rows


# Datasets-entry keys that are not a final map's limits.
_NOT_MAPS = {"intermediates", "feed", "measured", "reference_prefix", "candidate_prefix",
             "reference_set", "candidate_set"}


def final_maps(cfg: dict, phantom: str) -> list:
    """The final maps a pair × dataset has limits on (chimap; chi-para and chi-dia), in order. For
    an `intermediates_only` pair, the intermediates it has limits on (what its status shows)."""
    ds = ((cfg or {}).get("datasets") or {}).get(phantom) or {}
    if (cfg or {}).get("intermediates_only"):
        return list(ds.get("intermediates") or {})
    return [k for k, v in ds.items() if k not in _NOT_MAPS and isinstance(v, dict)]


def _summary(rec: "dict | None", finals: "list | None" = None) -> "dict | None":
    """A record as the status shows it. `nrmse` / `max_abs` are the worst over the final maps
    (`finals`, which have limits; else the record's first map, which is the final one)."""
    if not rec:
        return None
    metrics = rec.get("metrics") or {}
    maps = [metrics[n] for n in finals or [] if n in metrics] or [next(iter(metrics.values()), {})]
    final = maps[0]

    def worst(k):
        vs = [m[k] for m in maps if m.get(k) is not None]
        return max(vs) if vs else None
    out = {"date": rec.get("date"), "result": rec.get("result"), "run_url": rec.get("run_url"),
           "qsmrs": rec.get("qsmrs"), "qsmxt": {"commit": qsmxt_commit(rec)},
           "nrmse": worst("nrmse"), "max_abs": worst("max_abs"),
           "correlation": final.get("correlation"), "dice": final.get("dice")}
    if rec.get("release"):
        out["release"] = rec["release"]
    for k in ("dropped_feeds", "dropped_settings"):
        if rec.get(k):
            out[k] = rec[k]
    if rec.get("result") in ("fail", "error", "unavailable") and rec.get("failed"):
        out["why"] = rec["failed"][0]
    return out


def _tested(results: dict, track: str, release: "str | None" = None) -> list:
    """Which QSMxT / QSM.rs the newest records of a track ran, newest first: [{qsmxt, qsmrs,
    checks, date}] (a dev check refreshed one pair at a time can be on an older commit)."""
    groups: dict = {}
    for rec in latest_records(results, track, release).values():
        q = rec.get("qsmrs") or {}
        k = (qsmxt_commit(rec), q.get("commit"))
        g = groups.setdefault(k, {"qsmxt": {"ref": (rec.get("qsmxt") or {}).get("ref"),
                                            "commit": k[0]},
                                  "qsmrs": {"version": q.get("version"), "commit": q.get("commit")},
                                  "checks": 0, "date": ""})
        g["checks"] += 1
        g["date"] = max(g["date"], rec.get("date") or "")
    return sorted(groups.values(), key=lambda g: g["date"], reverse=True)


def release_history(thresholds: dict, results: dict) -> dict:
    """{pair: [{release, date, qsmxt, qsmrs, datasets: [{dataset, last}], badge}]}, newest release
    first: every released-track result per pair, for the site's history view and the per-release
    badges."""
    per: dict = {}
    for r in results.get("checks") or []:
        if record_track(r) == RELEASED and r.get("release"):
            per.setdefault(r.get("pair"), {}).setdefault(r["release"], []).append(r)
    out = {}
    for pair, by_rel in per.items():
        cfg = thresholds.get(pair) or {}
        entries = []
        for tag in sorted(by_rel, key=release_key, reverse=True):
            recs = sorted(by_rel[tag], key=lambda r: r.get("dataset") or "")
            dss = [{"dataset": r.get("dataset"), "last": _summary(r, final_maps(cfg, r.get("dataset")))}
                   for r in recs]
            row = {"state": "current", "datasets": dss}
            entries.append({"release": tag, "date": max(r.get("date") or "" for r in recs),
                            "qsmxt": {"ref": tag, "commit": qsmxt_commit(recs[0])},
                            "qsmrs": recs[0].get("qsmrs"), "datasets": dss,
                            "badge": badge(row, RELEASED, tag)})
        out[pair] = entries
    return out


def status_doc(thresholds: dict, results: dict, manifests: dict, settings: dict, *, today: str,
               release: "str | None", release_source: str = "", changes=None, qsmxt_changes=None,
               no_original: "dict | None" = None, checked: bool = False) -> dict:
    """parity/status.json: both tracks (rows, stale pairs, what each tested), the released-track
    history per pair, and the releases recorded. The site shows `default_track` first."""
    rel_rows = pair_status(thresholds, results, manifests, settings, no_original=no_original,
                           track=RELEASED, release=release)
    dev_rows = pair_status(thresholds, results, manifests, settings, changes, qsmxt_changes,
                           no_original, track=DEV)
    tested = _tested(results, RELEASED, release) if release else []
    return {
        "schema": 2, "generated": today, "default_track": RELEASED,
        "badges": f"{settings['site_url'].rstrip('/')}/parity/badges/",
        "tracks": {
            RELEASED: {"label": "Released",
                       "release": release, "release_source": release_source,
                       "qsmxt": {"repo": settings["qsmxt_repo"], "release": release,
                                 "commit": tested[0]["qsmxt"]["commit"] if tested else None},
                       "qsmrs": {"repo": settings["qsmrs_repo"],
                                 **(tested[0]["qsmrs"] if tested else {"version": None,
                                                                       "commit": None})},
                       "stale": [r["pair"] for r in rel_rows if r["state"] == "stale"],
                       "rerun": [r["pair"] for r in rel_rows
                                 if any(d.get("rerun") for d in r["datasets"])],
                       "pairs": rel_rows},
            DEV: {"label": "Development",
                  "qsmrs": {"repo": settings["qsmrs_repo"], "branch": settings["qsmrs_branch"],
                            "checked": checked},
                  "qsmxt": {"repo": settings["qsmxt_repo"], "branch": settings["qsmxt_branch"],
                            "checked": checked},
                  "tested": _tested(results, DEV),
                  "stale": [r["pair"] for r in dev_rows if r["state"] == "stale"],
                  "pairs": dev_rows},
        },
        "releases": recorded_releases(results),
        "history": release_history(thresholds, results),
    }


# ---------------------------------------------------------------------------------------------------
# Badges: shields.io endpoint files (https://shields.io/badges/endpoint-badge), published with the
# site under <site_url>/parity/badges/:
#   <name>.json                  the released track (the latest QSMxT release): the QSM.rs README's
#   dev/<name>.json              the development track
#   release/<tag>/<name>.json    each release's own result
# ---------------------------------------------------------------------------------------------------

BADGE_COLOR = {"current": "brightgreen", "stale": "orange", "failing": "red", "gap": "yellow",
               "unchecked": "lightgrey", "off": "lightgrey", "no-original": "lightgrey",
               "unavailable": "lightgrey"}


def _day(date: "str | None") -> str:
    """'2026-10-30T…' → '30 Oct'."""
    from datetime import date as _date
    try:
        d = _date.fromisoformat((date or "")[:10])
    except ValueError:
        return "?"
    return f"{d.day} {d:%b}"


def _nrmse_label(v: float) -> str:
    if v < 0.001:
        return "< 0.001 %"
    return f"{float(f'{v:.2g}'):g} %"


def badge(row: dict, track: str = DEV, release: "str | None" = None) -> dict:
    """{"kind", "message", "color"} for a status row.

    Dev track (dated by the oldest last check):
      current      green  "<NRMSE> · <date>" (worst final-map NRMSE over the datasets; "identical"
                          when every map is bit-identical);
      failing      red    an enabled pair whose last check failed or ended without a result;
      stale        orange "stale · <date of the oldest last check>";
      unchecked    grey   an enabled pair never checked on any dataset.
    Released track (labelled by the release, e.g. v10.0.0):
      current      green  "<NRMSE> · v10.0.0";
      failing      red    "failing · v10.0.0";
      unavailable  grey   "not in v10.0.0": the release has no such command or option;
      stale        orange "stale · v10.0.0": the reference or the pair's settings changed since;
      unchecked    grey   "not checked · v10.0.0": no run against the release yet.
      A result the release reached without one of the pair's optional feeds or `candidate_set`
      settings (its qsmxt has no option for it) says so: "65.9 % · v10.0.0 · no reliability, no
      offset_grid".
    Both:
      gap          yellow a disabled pair `blocked_by` a known gap: "gap · <issue>";
      off          grey   a disabled pair without a known gap: "not enabled";
      no-original  grey   a QSM.rs method with no original code to check against."""
    state = row["state"]
    released = track == RELEASED
    lasts = [d["last"] for d in row.get("datasets") or [] if d.get("last")]
    oldest = min((l.get("date") or "" for l in lasts), default="")
    when = (release or "release") if released else None
    if state == "no-original":
        kind, msg = "no-original", "no original"
    elif state == "off":
        kind, msg = "off", "not enabled"
    elif state == "gap":
        ref = str(row.get("blocked_by") or "")
        ref = ref.split("/", 1)[1] if "/" in ref else ref       # QSMxT/QSM-CI#311 → QSM-CI#311
        kind, msg = "gap", ("gap · " + ref) if ref else "gap"
    elif not lasts:
        kind, msg = "unchecked", (f"not checked · {when}" if released and release
                                  else "not yet checked")
    elif any(l.get("result") in ("fail", "error") or (not released and l.get("result") != "pass")
             for l in lasts):
        bad = min((l.get("date") or "" for l in lasts if l.get("result") != "pass"), default="")
        kind, msg = "failing", f"failing · {when or _day(bad)}"
    elif any(l.get("result") == "unavailable" for l in lasts):
        kind, msg = "unavailable", f"not in {when}"
    elif state == "stale":
        kind, msg = "stale", f"stale · {when or _day(oldest)}"
    else:
        nrmse = [l["nrmse"] for l in lasts if l.get("nrmse") is not None]
        identical = nrmse and all(l.get("nrmse") == 0 and not l.get("max_abs") for l in lasts)
        kind = "current"
        msg = ("identical" if identical else _nrmse_label(max(nrmse)) if nrmse else "pass") \
            + f" · {when or _day(oldest)}"
    # the release ran without an optional feed or a candidate setting its qsmxt has no option for
    dropped = sorted({f for l in lasts for f in l.get("dropped_feeds") or []}) \
        + sorted({f for l in lasts for f in l.get("dropped_settings") or []})
    if dropped and kind in ("current", "failing", "stale"):
        msg += " · " + ", ".join(f"no {d}" for d in dropped)
    return {"kind": kind, "message": msg, "color": BADGE_COLOR[kind]}


def badge_endpoint(b: dict) -> dict:
    """The shields.io endpoint JSON for a row's badge."""
    return {"schemaVersion": 1, "label": "parity", "message": b["message"], "color": b["color"]}


GENERIC_BADGES = {   # for a README row with no pair and no no_original entry
    "not-checked": {"kind": "unchecked", "message": "not yet checked", "color": "lightgrey"},
}


def _write_badge_dir(want: dict, out: Path) -> None:
    """<out>/<name>.json per {name: badge}; other .json files directly in <out> are removed."""
    out.mkdir(parents=True, exist_ok=True)
    for f in out.glob("*.json"):
        if f.stem not in want:
            f.unlink()
    for name, b in want.items():
        (out / f"{name}.json").write_text(json.dumps(badge_endpoint(b)) + "\n")


def write_badges(doc: dict, out: Path) -> list:
    """Every badge file of a status_doc under `out` (see the section comment); returns the paths
    written, relative to `out`. Files of pairs, tracks or releases that no longer exist go."""
    import shutil
    out = Path(out)
    written = []
    for sub, track in (("", RELEASED), ("dev", DEV)):
        want = {r["pair"]: r["badge"] for r in doc["tracks"][track]["pairs"]}
        for k, v in GENERIC_BADGES.items():
            want.setdefault(k, v)
        _write_badge_dir(want, out / sub if sub else out)
        written += [f"{sub + '/' if sub else ''}{n}.json" for n in want]
    if (out / "release").exists():
        shutil.rmtree(out / "release")
    for pair, entries in (doc.get("history") or {}).items():
        for e in entries:
            d = out / "release" / e["release"]
            d.mkdir(parents=True, exist_ok=True)
            (d / f"{pair}.json").write_text(json.dumps(badge_endpoint(e["badge"])) + "\n")
            written.append(f"release/{e['release']}/{pair}.json")
    return sorted(written)


STATE_LABEL = {"current": "✅ current", "stale": "⚠️ stale", "gap": "🚧 gap", "off": "— not enabled"}
RESULT_LABEL = {"pass": "✅ pass", "fail": "❌ fail", "error": "❌ error",
                "unavailable": "⚪ not in release"}


def _tested_line(track: str, block: dict) -> str:
    if track == RELEASED:
        rel = block.get("release")
        if not rel:
            return "No QSMxT release is known yet."
        q = block.get("qsmrs") or {}
        pin = (f"QSM.rs {'v' + q['version'] + ' ' if q.get('version') else ''}`{_short(q['commit'])}`"
               if q.get("commit") else "the QSM.rs it pins (not recorded yet: no run against it)")
        return f"Tested: QSMxT **{rel}** (the binary the release ships) with {pin}."
    tested = block.get("tested") or []
    if not tested:
        return "Tested: nothing recorded yet."
    t = tested[0]
    more = f" ({len(tested) - 1} older build(s) for pairs not rerun since)" if len(tested) > 1 else ""
    return (f"Tested: QSMxT main `{_short(t['qsmxt']['commit'])}` with qsm-core at QSM.rs main "
            f"`{_short(t['qsmrs']['commit'])}`{more}.")


def _status_table(rows: list, track: str) -> list:
    lines = ["| Pair | Original → port | Dataset | Last check | QSM.rs | Result | NRMSE | Status |",
             "|---|---|---|---|---|---|---|---|"]
    for r in [r for r in rows if r["state"] != "no-original"]:
        dss = r["datasets"] or [{"dataset": "—", "last": None, "stale": r["enabled"],
                                 "reasons": ["no dataset configured"] if r["enabled"] else []}]
        for i, d in enumerate(dss):
            last = d["last"] or {}
            when = (f"[{last['date'][:10]}]({last['run_url']})" if last.get("run_url")
                    else (last.get("date") or "")[:10]) if last else "never"
            res = RESULT_LABEL.get(last.get("result"), "—")
            if last.get("result") == "unavailable":
                res = f"⚪ not in {last.get('release') or 'release'}"
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
    return lines


def render_status(doc: dict) -> str:
    """parity/STATUS.md: both tracks' tables, regenerated by the parity workflows."""
    rel, dev = doc["tracks"][RELEASED], doc["tracks"][DEV]
    tag = rel.get("release")
    lines = ["# Port parity status", "",
             f"Generated {doc['generated']} by `scripts/parity.py status` from `parity/results.json` "
             "and `parity/thresholds.yml`; do not edit by hand. How checks run, the two tracks, and "
             "what makes a check stale: [docs/parity.md](../docs/parity.md).", "",
             f"## Released: QSMxT {tag or '(no release yet)'}", "",
             _tested_line(RELEASED, rel), "",
             "The latest QSMxT release against each verified original. A release does not change, so "
             "it is rerun only for a new release, or when a pair's reference image or settings "
             "change. A failure here is that release's result; **not in** means the release has no "
             "such command or option yet.", ""]
    lines += _status_table(rel["pairs"], RELEASED)
    if rel.get("stale") and tag:
        lines += ["", f"Run the flagged pairs against {tag}:", "", "```bash",
                  refresh_command(rel["stale"], RELEASED, tag), "```"]
    lines += ["", "## Development: QSMxT main × QSM.rs main", "", _tested_line(DEV, dev), "",
              "A check is **stale** when the reference image changed, QSM.rs `main` changed the "
              "port's source files or `Cargo.lock`, QSMxT `main` changed the step's wiring or "
              "`Cargo.lock`, the pair's limits changed, or it failed. There is no age limit. A "
              "**gap** is a pair whose port does not match its original yet: it is not enabled, "
              "and has no limits that would pass it.", ""]
    lines += _status_table(dev["pairs"], DEV)
    if dev.get("stale"):
        lines += ["", "Refresh every stale pair against QSM.rs `main`:", "", "```bash",
                  refresh_command(dev["stale"]), "```"]
    none = [r for r in dev["pairs"] if r["state"] == "no-original"]
    if none:
        lines += ["", "## No original", "",
                  "No original code to check against (QSMxT/QSM-CI#302; tested against ground "
                  "truth in QSM.rs instead):", "", "| Method | Covers | Note |", "|---|---|---|"]
        lines += [f"| `{r['pair']}` | {r.get('covers') or ''} | {r.get('note') or ''} |" for r in none]
    hist = doc.get("history") or {}
    if hist:
        lines += ["", "## Release history", "", "| Pair | " + " | ".join(doc["releases"]) + " |",
                  "|---|" + "---|" * len(doc["releases"])]
        for pair in sorted(hist):
            by = {e["release"]: e["badge"]["message"] for e in hist[pair]}
            lines.append(f"| `{pair}` | " + " | ".join(by.get(t, "—") for t in doc["releases"]) + " |")
    return "\n".join(lines) + "\n"


def render_issue(doc: dict) -> str:
    """The tracking issue's body, one section per track with something flagged; empty when
    nothing is (the workflow then closes it)."""
    today = doc["generated"]
    rel, dev = doc["tracks"][RELEASED], doc["tracks"][DEV]
    flagged = {t: [r for r in doc["tracks"][t]["pairs"] if r["state"] == "stale"] for t in TRACKS}
    if not any(flagged.values()):
        return ""
    lines = ["<!-- parity-status: kept up to date by .github/workflows/parity-status.yml; edits "
             "are overwritten -->",
             f"**Owner: QSM-CI.** As of {today} (rules: docs/parity.md, \"Tracks\" and "
             "\"Staleness\"; full tables: [parity/STATUS.md](../blob/main/parity/STATUS.md)).", ""]
    tag = rel.get("release")
    if flagged[RELEASED]:
        n = len(flagged[RELEASED])
        lines += [f"### Released: QSMxT {tag}", "",
                  f"{n} enabled pair{'s need' if n != 1 else ' needs'} a run against {tag} (none "
                  "yet, or the reference or settings changed since; parity-release.yml reruns "
                  "those daily) or ended without a result.", ""]
        for r in flagged[RELEASED]:
            lines.append(f"- **`{r['pair']}`**: " + "; ".join(
                f"{d['dataset']}: {', '.join(d['reasons'])}" for d in r["datasets"] if d["stale"]))
        lines += ["", "```bash", refresh_command([r["pair"] for r in flagged[RELEASED]], RELEASED,
                                                 tag), "```", ""]
    if flagged[DEV]:
        n = len(flagged[DEV])
        lines += ["### Development: QSMxT main × QSM.rs main", "",
                  f"{n} enabled pair{'s are' if n != 1 else ' is'} stale.", ""]
        for r in flagged[DEV]:
            lines.append(f"- **`{r['pair']}`** (`{r['reference']}` → `{r['candidate']}`)")
            for d in r["datasets"]:
                if d["stale"]:
                    lines.append(f"  - {d['dataset']}: " + "; ".join(d["reasons"]))
            lines.append(f"  - refresh: `{r['refresh']}`")
        lines += ["", "Refresh them all against QSM.rs `main` (a run from `main` records its result, "
                  "and this issue closes when nothing is flagged):", "", "```bash",
                  refresh_command([r["pair"] for r in flagged[DEV]]), "```"]
    return "\n".join(lines) + "\n"


def render_run_summary(records: list, enabled: list, baseline: bool = False) -> str:
    """The run's summary (the workflow's report job): one row per pair × dataset, then the answer
    the run's track needs. Dev: the release gate (which pairs passed against exactly the QSM.rs
    commit under test). Released: what the release passed, failed and does not have."""
    lines = ["## Parity run summary", ""]
    release = next((r.get("release") for r in records if r.get("release")), None)
    if release:
        lines += [f"Released track: QSMxT **{release}**.", ""]
    commits = sorted({(r.get("qsmrs") or {}).get("commit") or "?" for r in records})
    lines += ["| Pair | Dataset | Result | QSM.rs | QSMxT | NRMSE | r |", "|---|---|---|---|---|---|---|"]
    for r in records:
        m = next(iter((r.get("metrics") or {}).values()), {})   # the final map comes first
        res = {"pass": "✅ pass", "fail": "❌ fail", "error": "❌ no result",
               "unavailable": f"⚪ not in {release}",
               "baseline": "📏 baseline"}.get(r.get("result"), r.get("result"))
        qx = r.get("qsmxt") or {}
        lines.append(f"| `{r['pair']}` | {r['dataset']} | {res} | {_qsmrs_label(r)} "
                     f"| {('`' + _short(qx.get('commit')) + '`') if qx.get('commit') else (r.get('candidate') or {}).get('qsmxt') or '—'} "
                     f"| {_fmt(m.get('nrmse'), 'nrmse')} | {_fmt(m.get('correlation'))} |")
    if baseline:
        return "\n".join(lines + ["", "Baseline run: no limits applied, nothing recorded."]) + "\n"
    lines.append("")
    if release:
        by = {k: sorted({r["pair"] for r in records if r.get("result") in v})
              for k, v in (("bad", ("fail", "error")), ("missing", ("unavailable",)))}
        ok = sorted({r["pair"] for r in records} - set(by["bad"]) - set(by["missing"]))
        lines.append(f"**QSMxT {release}:** passed on every dataset run: "
                     + (", ".join(f"`{p}`" for p in ok) or "none") + ".")
        if by["bad"]:
            lines.append(f"Failed or no result: {', '.join(f'`{p}`' for p in by['bad'])}.")
        if by["missing"]:
            lines.append(f"Not in {release}: {', '.join(f'`{p}`' for p in by['missing'])}.")
        for r in records:
            if r.get("result") == "unavailable" and r.get("failed"):
                lines.append(f"- `{r['pair']}` {r['dataset']}: {r['failed'][0]}")
        return "\n".join(lines) + "\n"
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


# ---------------------------------------------------------------------------------------------------
# Released track: does the release have the port at all? (`parity.py unavailable`)
# ---------------------------------------------------------------------------------------------------

def port_commands(run_sh: str) -> list:
    """The qsmxt subcommands a port's run.sh calls (`qsmxt invert star …` → ["invert", "star"];
    `qsmxt qsmart "$IN/…"` → ["qsmart"]), in order, without duplicates. Comment lines are skipped."""
    import re
    call = re.compile(r"(?:^|[;&|(!]\s*|\bexec\s+|\bthen\s+|\bif\s+|\$\(\s*)"
                      r"qsmxt((?:\s+[a-z][a-z0-9-]*){1,2})")
    out = []
    for line in run_sh.splitlines():
        s = line.strip()
        if s.startswith("#"):
            continue
        for m in call.finditer(s):
            cmd = m.group(1).split()
            if cmd not in out:
                out.append(cmd)
    return out


def missing_command(image: str, runner: str, commands: list) -> "str | None":
    """The first of `commands` the qsmxt in `image` does not have (`qsmxt <cmd> --help` fails), as
    "qsmxt invert star"; None when it has them all."""
    for cmd in commands:
        r = subprocess.run([runner, "run", "--rm", "--network", "none", "--entrypoint", "qsmxt",
                            image, *cmd, "--help"], capture_output=True, text=True)
        if r.returncode != 0:
            return "qsmxt " + " ".join(cmd)
    return None


def clap_rejection(log: str) -> "str | None":
    """qsmxt's own refusal of a command line, from a run's log: clap's `unrecognized subcommand`,
    `unexpected argument` or `invalid value` error (a subcommand, option or option value the
    release does not have), or its `the following required arguments were not provided` (the
    release's command needs an input the port no longer passes: an earlier, different port, e.g.
    qsmxt v10.0.0's paper-based `separate chi-sep-ilsqr --magnitude`); None for any other failure."""
    import re
    m = re.search(r"error: (unrecognized subcommand '[^']*'|unexpected argument '[^']*' found"
                  r"|invalid value '[^']*' for '[^']*')", log or "")
    if m:
        return m.group(1)
    m = re.search(r"error: the following required arguments were not provided:\n((?:[ \t]+\S.*\n?)+)",
                  log or "")
    if m:
        args = ", ".join(a.split()[0] for a in m.group(1).splitlines() if a.strip())
        return f"required argument not provided: {args}"
    return None


def cmd_unavailable(args) -> int:
    """Released track only: write parity.json saying the release does not have the pair's port —
    before the run (`--qsmrs-image`: a QSM.rs step's subcommand is missing) or after a failed run
    (`--log`: qsmxt refused the command line). Writes nothing when the port is there (or the
    failure was something else); exits 0 either way, so the workflow tests for the file."""
    th = load_thresholds(args.thresholds)
    cfg = pair_config(th, args.algorithm, validate=False)
    manifests = _manifests()
    why = None
    if args.log:
        hit = clap_rejection(Path(args.log).read_text(errors="replace"))
        if hit:
            why = f"QSMxT {args.release} refuses the port's command line: {hit}"
    else:
        slugs = [s for side in ("reference", "candidate") for s in side_chain(cfg, side, args.phantom)
                 if is_port(manifests.get(s) or {})]
        for slug in dict.fromkeys(slugs):
            run_sh = ROOT / "algorithms" / slug / "run.sh"
            cmds = port_commands(run_sh.read_text()) if run_sh.exists() else []
            miss = missing_command(args.qsmrs_image, args.runner, cmds)
            if miss:
                why = f"QSMxT {args.release} has no `{miss}` ({slug})"
                break
    if not why:
        print(f"{args.algorithm}: the port is in QSMxT {args.release}")
        return 0
    print(f"{args.algorithm}: {why}")
    ident = image_identity(args.qsmrs_image, args.runner) if args.qsmrs_image else {}
    Path(args.json).write_text(json.dumps({
        "algorithm": args.algorithm, "phantom": args.phantom, "reference": cfg["reference"],
        "candidate": cfg["candidate"], "baseline": False, "unavailable": why,
        "provenance": {"candidate": {"steps": [{"slug": cfg["candidate"],
                                                "image": args.qsmrs_image, **ident}]}},
    }, indent=2) + "\n")
    if args.report:
        Path(args.report).write_text(f"## Parity: `{args.algorithm}` on {args.phantom}\n\n"
                                     f"⚪ **Not in QSMxT {args.release}**: {why}.\n")
    return 0


# ---------------------------------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------------------------------

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
           "qsmxt_ref": args.qsmxt_ref, "track": args.track, "release": args.release or None}
    if args.track == RELEASED and not args.release:
        raise SystemExit("report: the released track needs --release")
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


def latest_release(args, settings: dict, results: dict, token: "str | None") -> "tuple":
    """(tag, source): `--latest-release`, else GitHub's latest QSMxT release (online), else the
    newest release the released track has records for."""
    if getattr(args, "latest_release", None):
        return args.latest_release, "given"
    if not getattr(args, "offline", False):
        tag = github_latest_release(settings["qsmxt_repo"], token)
        if tag:
            return tag, "github"
    rec = recorded_releases(results)
    return (rec[0], "records") if rec else (None, "")


def cmd_status(args) -> int:
    from datetime import datetime, timezone
    th = load_thresholds(args.thresholds)
    settings = load_settings(args.thresholds)
    today = args.today or datetime.now(timezone.utc).date().isoformat()
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    changes = qsmxt_changes = None
    if not args.offline:
        changes = lambda c: github_compare(settings["qsmrs_repo"], c, settings["qsmrs_branch"], token)  # noqa: E731
        qsmxt_changes = lambda c: github_compare(settings["qsmxt_repo"], c, settings["qsmxt_branch"],  # noqa: E731
                                                 token)
    results = load_results(args.results)
    release, source = latest_release(args, settings, results, token)
    doc = status_doc(th, results, _manifests(), settings, today=today, release=release,
                     release_source=source, changes=changes, qsmxt_changes=qsmxt_changes,
                     no_original=load_no_original(args.thresholds), checked=not args.offline)
    if args.json:
        Path(args.json).write_text(json.dumps(doc, indent=1, default=str) + "\n")
    md = render_status(doc)
    if args.markdown:
        Path(args.markdown).write_text(md)
    if args.issue:
        Path(args.issue).write_text(render_issue(doc))
    if args.badges:
        write_badges(doc, args.badges)
    if not (args.json or args.markdown or args.issue or args.badges):
        print(md)
    else:
        print(f"released {release or '(none)'}: flagged {', '.join(doc['tracks'][RELEASED]['stale']) or 'none'}; "
              f"dev stale: {', '.join(doc['tracks'][DEV]['stale']) or 'none'}")
    return 0


def cmd_badges(args) -> int:
    """The badge files from an existing status.json (what pages.yml publishes): no GitHub calls,
    so the site always shows the badges of the status it serves."""
    doc = json.loads(Path(args.status).read_text())
    if "tracks" not in doc:
        raise SystemExit(f"{args.status}: no `tracks` (a status.json from before the two tracks); "
                         "regenerate it with `parity.py status`")
    for track in TRACKS:   # from the rows, so a change to `badge` shows at the next deploy
        block = doc["tracks"][track]
        for r in block.get("pairs") or []:
            r["badge"] = badge(r, track, block.get("release"))
    for entries in (doc.get("history") or {}).values():
        for e in entries:
            e["badge"] = badge({"state": "current", "datasets": e["datasets"]}, RELEASED, e["release"])
    names = write_badges(doc, args.out)
    print(f"{len(names)} badge(s) in {args.out}")
    return 0


def cmd_released_plan(args) -> int:
    """What parity-release.yml should dispatch on the released track, as JSON {release, algorithm,
    why}: every enabled pair for a release with no records yet, else the pairs whose reference image
    or settings changed since their run against it (or that never ran on a dataset); `algorithm`
    is empty when nothing needs a run."""
    th = load_thresholds(args.thresholds)
    settings = load_settings(args.thresholds)
    results = load_results(args.results)
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    release, source = latest_release(args, settings, results, token)
    if not release:
        print(json.dumps({"release": None, "algorithm": "", "why": "no QSMxT release found"}))
        return 0
    if release not in recorded_releases(results):
        out = {"release": release, "algorithm": "enabled",
               "why": f"no released-track records for QSMxT {release} yet"}
    else:
        rows = pair_status(th, results, _manifests(), settings, track=RELEASED, release=release)
        rerun = [r["pair"] for r in rows if any(d.get("rerun") for d in r["datasets"])]
        out = {"release": release, "algorithm": ",".join(rerun),
               "why": "; ".join(f"{r['pair']}: " + ", ".join(sorted({x for d in r["datasets"]
                                                                       for x in d["reasons"]}))
                                for r in rows if r["pair"] in rerun) or "nothing to rerun"}
    out["source"] = source
    print(json.dumps(out))
    return 0


def active_release_runs(runs: list, release: str, jobs_of) -> list:
    """The ids of parity.yml runs (GitHub API run objects) that are a released run for `release`
    and still going: queued or in progress, and not being cancelled. GitHub keeps a cancelled run
    `in_progress` until its jobs stop, so a run with any job already concluded `cancelled` counts
    as gone (`jobs_of(run_id)` lists its jobs). parity.yml's run name says `released <tag>`."""
    out = []
    for r in runs or []:
        if r.get("status") == "completed" or r.get("conclusion") in ("cancelled", "skipped"):
            continue
        if f"released {release} " not in (r.get("display_title") or "") + " ":
            continue
        if any(j.get("conclusion") == "cancelled" for j in jobs_of(r.get("id")) or []):
            continue
        out.append(r.get("id"))
    return out


def cmd_released_busy(args) -> int:
    """Print the ids of released parity runs for --release still queued or running (one per line;
    nothing when none), from GitHub's API. parity-release.yml dispatches only when this is empty."""
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    base = f"https://api.github.com/repos/{args.repo}/actions"
    doc, err = _gh_get(f"{base}/workflows/parity.yml/runs?per_page=50", token)
    if err:
        raise SystemExit(f"released-busy: listing parity.yml runs: {err[1]}")

    def jobs_of(run_id):
        d, e = _gh_get(f"{base}/runs/{run_id}/jobs?per_page=100", token)
        return [] if e else (d or {}).get("jobs") or []
    for i in active_release_runs((doc or {}).get("workflow_runs") or [], args.release, jobs_of):
        print(i)
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
    for k in ("date", "run-id", "run-url", "qsmci-commit", "qsmrs-ref", "qsmxt-ref", "release"):
        p.add_argument(f"--{k}", default="")
    p.add_argument("--track", choices=TRACKS, default=DEV)
    p.add_argument("--baseline", action="store_true")
    p.add_argument("--out", type=Path, help="write the records (JSON list) here")
    p.add_argument("--summary", type=Path, help="write the run summary (markdown) here")
    p.set_defaults(fn=cmd_report)
    p = sub.add_parser("record", help="append a run's records to parity/results.json")
    p.add_argument("--records", type=Path, required=True)
    p.add_argument("--results", type=Path, default=RESULTS)
    p.set_defaults(fn=cmd_record)
    for name, fn, hlp in (("status", cmd_status, "last check and staleness per pair, both tracks"),
                          ("released-plan", cmd_released_plan,
                           "what the released track needs to run (parity-release.yml)")):
        p = sub.add_parser(name, help=hlp)
        p.add_argument("--results", type=Path, default=RESULTS)
        p.add_argument("--latest-release", help="the latest QSMxT release tag (default: ask GitHub)")
        p.add_argument("--offline", action="store_true",
                       help="no GitHub calls: skip rules (b) and (f), and take the latest release "
                            "from --latest-release or the records")
        p.set_defaults(fn=fn)
        if name == "status":
            p.add_argument("--json", type=Path, help="e.g. parity/status.json")
            p.add_argument("--markdown", type=Path, help="e.g. parity/STATUS.md")
            p.add_argument("--issue", type=Path, help="the tracking issue's body (empty: nothing flagged)")
            p.add_argument("--badges", type=Path, help="write the shields.io endpoint files here")
            p.add_argument("--today", help="YYYY-MM-DD (default: today, UTC)")
    p = sub.add_parser("released-busy", help="released parity runs for a release still queued or "
                                             "running, not being cancelled (parity-release.yml)")
    p.add_argument("--release", required=True)
    p.add_argument("--repo", default=REPO)
    p.set_defaults(fn=cmd_released_busy)
    p = sub.add_parser("badges", help="the badge files from a status.json (the site deploy)")
    p.add_argument("--status", type=Path, default=ROOT / "parity" / "status.json")
    p.add_argument("--out", type=Path, required=True)
    p.set_defaults(fn=cmd_badges)
    p = sub.add_parser("rejected-setting", help="released track: the candidate_set key a failed "
                                                "run's qsmxt refused (printed; nothing if none)")
    p.add_argument("--algorithm", required=True)
    p.add_argument("--phantom", default="sim")
    p.add_argument("--log", type=Path, required=True)
    p.set_defaults(fn=lambda a: print(rejected_setting(
        pair_config(load_thresholds(a.thresholds), a.algorithm, validate=False), a.phantom,
        Path(a.log).read_text(errors="replace")) or "") or 0)
    p = sub.add_parser("unavailable", help="released track: write parity.json if the release lacks "
                                           "the pair's port")
    p.add_argument("--algorithm", required=True)
    p.add_argument("--phantom", default="sim")
    p.add_argument("--release", required=True)
    p.add_argument("--qsmrs-image", help="the release's qsmxt image (the check before the run)")
    p.add_argument("--runner", default="docker", choices=["docker", "podman"])
    p.add_argument("--log", type=Path, help="a failed run's log (the check after it)")
    p.add_argument("--json", type=Path, required=True)
    p.add_argument("--report", type=Path)
    p.set_defaults(fn=cmd_unavailable)
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
            p.add_argument("--candidate-only", action="store_true",
                           help="rerun only the candidate, against the reference output in --work")
            p.add_argument("--drop-optional-feeds", action="store_true",
                           help="run the candidate without the pair's optional feeds (exit 3 if "
                                "nothing is dropped)")
            p.add_argument("--drop-setting", action="append", metavar="KEY",
                           help="run the candidate without this candidate_set key (repeatable)")
        else:
            p.add_argument("--mask", type=Path, help="default: <dataset>/inputs/mask.nii.gz")
            p.add_argument("--baseline", action="store_true",
                           help="measure and suggest limits; never fail on them")
            p.add_argument("--note", default="", help="a line for the report, e.g. which QSM.rs "
                                                          "build the candidate ran")
            p.add_argument("--report", type=Path)
            p.add_argument("--json", type=Path)
    args = ap.parse_args(argv)
    if args.cmd == "unavailable" and not (args.log or args.qsmrs_image):
        ap.error("unavailable: give --qsmrs-image (before the run) or --log (after it)")
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
