#!/usr/bin/env python3
"""Plan a score.yml run: decide WHAT needs scoring and turn it into a matrix of runner tasks.

This is the `plan` job of .github/workflows/score.yml, pulled out of the workflow so its logic is
unit-testable (tests/test_score_plan.py) and readable. It replaces the two inline shell/python
blocks that used to make up the `scope` and `plan` jobs.

What needs scoring ("scope")
----------------------------
The old rule — "diff this push against its previous head" — silently lost work: score runs share a
concurrency group, GitHub keeps at most ONE pending run per group, and a newer push cancels the
older pending run. The survivor only ever looked at its OWN push, so the displaced push's changed
methods were never scored (observed 2026-09-04: hd-bet-qsmci + amp-pe). Now the scope is:

    everything changed on main since the last COMPLETED scoring (results/scoring-state.json)
    ∪ whatever a previous run planned but did not finish (its `pending` list)
    − tasks another still-running score run is already covering at an up-to-date commit

so a displaced, cancelled, timed-out or failed run's work is picked up by the next run instead of
disappearing, and a burst of pushes never restarts a task that is already being scored correctly.
Per-commit `[skip score]` is honoured commit by commit (a documented no-op change stays a no-op
even when it is bundled with later real changes), and an algorithm.yml edit that cannot change a
number (description, authors, runner tier, …) does not rescore the method (see SCORE_COSMETIC).

Where each task runs ("route")
------------------------------
Per-method `runner:` in algorithm.yml:
    (unset)       HOSTED       ubuntu-latest, 360-min cap (GitHub's 6-h max), 2 containers. Scored
                               inside the parallel shard sweep on a full re-run.
    hosted-large  HOSTED_LARGE ubuntu-latest, 360-min cap, 1 container (the full 16 GB).
    self-hosted   SELFHOSTED   QSM-CI's private runners (31 GB, the only tier that may exceed 6 h via
                               `timeout_minutes:`). Own focus job; excluded from the shard sweep.
    manual | gpu  MANUAL       NEVER scheduled automatically (not on push, not by scope=all). Scored
                               only when a workflow_dispatch names the slug in `scope`, or with
                               include_manual=true. For methods whose CPU cost makes them infeasible
                               on the shared box (MoDIP ≈ 12 h per inversion, INR-QSM ≈ 17 h) — a
                               cap cannot fix that, and every automatic attempt burned a runner for
                               its whole cap and produced nothing. `gpu` also documents the
                               hardware requirement for when a GPU runner exists.
Per-method overrides, honoured on self-hosted/manual only (hosted tiers are hard-capped by GitHub):
    timeout_minutes: N   wall-clock cap for the job
    jobs: N              concurrent containers inside the job (default 4 on self-hosted; set 1 for a
                         method that already uses every core, so runs don't contend with each other)
    manual_phantoms: []  phantom ids this method is scored on ONLY when explicitly dispatched (e.g.
                         DECOMPOSE on the 5M-voxel ridani-3t-iso phantom exceeds 12 h; the smaller
                         phantoms stay automatic)

Environment (set by score.yml):
    EVENT, SHA, BEFORE, SCOPE, INCLUDE, SHARDS, INCLUDE_MANUAL, RUN_ID, REPO, GH_TOKEN (optional)
Outputs (GITHUB_OUTPUT): tasks=<json list>, full=true|false, slugs=<json list>, base=<sha>
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from ci_eval_targets import COSMETIC_KEYS  # noqa: E402

STATE_PATH = "results/scoring-state.json"
# Paths whose change re-scores everything (the scorer / orchestration). Mirrors score.yml's `paths:`
# trigger list minus algorithms/**, which scopes to the touched slugs.
FULL_TRIGGER = re.compile(r"^(eval/|scripts/pipeline\.py|scripts/publish_volumes\.py|stages\.yml)")
SKIP_TOKEN = "[skip score]"
# algorithm.yml keys whose edit cannot move a score: the evaluate gate's cosmetic set plus the
# scheduling knobs this planner reads itself. `compose:` is NOT here — it changes the matrix.
SCORE_COSMETIC = COSMETIC_KEYS | {"runner", "timeout_minutes", "jobs", "manual_phantoms",
                                  "smoke_box", "smoke_params", "ci_skip_reason"}

HOSTED = {"runs_on": "ubuntu-latest", "timeout": 360, "jobs": 2}
HOSTED_LARGE = {"runs_on": "ubuntu-latest", "timeout": 360, "jobs": 1}
SELFHOSTED = {"runs_on": ["self-hosted", "Linux", "X64"], "timeout": 360, "jobs": 4}
TIERS = {"": "hosted", "hosted": "hosted", "hosted-large": "hosted-large",
         "self-hosted": "self-hosted", "manual": "manual", "gpu": "manual"}


# ---------------------------------------------------------------------------------------------------
# algorithm.yml access
# ---------------------------------------------------------------------------------------------------

def _scalar(v):
    return v.strip("\"'") if isinstance(v, str) else v


def load_spec(root: Path, slug: str) -> dict | None:
    try:
        doc = yaml.safe_load((root / slug / "algorithm.yml").read_text())
    except (FileNotFoundError, yaml.YAMLError):
        return None
    return doc if isinstance(doc, dict) else None


def all_slugs(root: Path) -> list[str]:
    return sorted(p.parent.name for p in root.glob("*/algorithm.yml") if not p.parent.name.startswith("_"))


def tier_of(spec: dict | None) -> str:
    r = _scalar((spec or {}).get("runner")) or ""
    return TIERS.get(str(r), "hosted")


def route(spec: dict | None) -> dict:
    """Runner, cap and intra-job container count for a method's task."""
    tier = tier_of(spec)
    base = {"hosted": HOSTED, "hosted-large": HOSTED_LARGE, "self-hosted": SELFHOSTED,
            "manual": SELFHOSTED}[tier]
    out = dict(base)
    if tier in ("self-hosted", "manual"):
        for key, field in (("timeout", "timeout_minutes"), ("jobs", "jobs")):
            v = (spec or {}).get(field)
            if isinstance(v, int) and v > 0:
                out[key] = v
    return out


def stage_of(spec: dict | None) -> str | None:
    s = (spec or {}).get("stage")
    return str(_scalar(s)) if s is not None else None


def is_skipped(spec: dict | None) -> bool:
    return spec is None or bool(spec.get("ci_skip"))


def is_chisep(spec) -> bool:
    return stage_of(spec) in ("chi-separation", "r2prime-generation")


def is_dipole(spec) -> bool:
    return stage_of(spec) == "dipole"


def consumes_r2prime(spec) -> bool:
    inp = (spec or {}).get("inputs")
    return "r2prime" in [str(_scalar(a)) for a in inp] if isinstance(inp, list) else True


def manual_phantoms(spec) -> set[str]:
    v = (spec or {}).get("manual_phantoms")
    return {str(_scalar(x)) for x in v} if isinstance(v, list) else set()


# ---------------------------------------------------------------------------------------------------
# Task planning (pure)
# ---------------------------------------------------------------------------------------------------

def track_phantoms(reg: dict, track: str) -> list[str]:
    ph = [k for k, v in reg.items() if v.get("track") == track and v.get("active")]
    return sorted(ph, key=lambda k: (not reg[k].get("default"), k))  # default first


def task_id(reg: dict, prefix: str, slug: str, ph: str) -> str:
    return prefix + slug + ("" if reg[ph].get("default") else "-" + ph)


def phantoms_for(spec, reg: dict) -> list[str]:
    return track_phantoms(reg, "chisep") if is_chisep(spec) else ["sim"]


def dedicated(root: Path) -> list[str]:
    """Methods that run as their own focus job rather than inside the shard sweep: any non-hosted
    tier, or a χ-separation-track method (scored on separate phantoms)."""
    out = []
    for slug in all_slugs(root):
        spec = load_spec(root, slug)
        if tier_of(spec) != "hosted" or is_chisep(spec):
            out.append(slug)
    return out


def plan_tasks(root: Path, reg: dict, *, full: bool, slugs: list[str], include: str = "",
               shards: int = 12, explicit: set[str] | None = None,
               include_manual: bool = False) -> list[dict]:
    """The matrix for a run. `explicit` = slugs a human named on dispatch: they (and their manual
    phantoms) are planned even when their tier is manual. `include_manual` lifts that for everyone."""
    explicit = explicit or set()
    specs = {s: load_spec(root, s) for s in all_slugs(root)}

    def allowed(slug: str, ph: str | None = None) -> bool:
        spec = specs.get(slug)
        if is_skipped(spec):
            return False
        wanted = include_manual or slug in explicit
        if tier_of(spec) == "manual" and not wanted:
            return False
        if ph is not None and ph in manual_phantoms(spec) and not wanted:
            return False
        return True

    ded = dedicated(root)
    heavy_dipoles = ",".join(s for s in ded if is_dipole(specs[s]) and not is_skipped(specs[s]))

    def focus_tasks(sl: list[str]) -> list[dict]:
        tasks = []
        for s in sorted(set(sl)):
            spec = specs.get(s)
            if spec is None:
                continue
            for ph in phantoms_for(spec, reg):
                if not allowed(s, ph):
                    continue
                t = {"id": task_id(reg, "f-", s, ph), "focus": s, "phantom": ph, **route(spec)}
                # A non-dipole focus (a bfr/span) varies EVERY dipole; the heavy dedicated dipoles
                # would overrun its cap, and their combos are owned by their own focus jobs.
                if heavy_dipoles and not is_dipole(spec) and not is_chisep(spec):
                    t["exclude"] = heavy_dipoles
                tasks.append(t)
        return tasks

    def invivo_tasks(sl: list[str]) -> list[dict]:
        return [{"id": "iv-" + s, "focus": s, "phantom": "invivo", "track": "invivo", **route(specs[s])}
                for s in sorted(set(sl)) if s in specs and is_dipole(specs[s]) and allowed(s)]

    if include:
        return [{"id": "manual-include", "include": include, "mode": "composed", "phantom": "sim", **HOSTED}]
    if full:
        excl = ",".join(ded)
        tasks = [{"id": "s%02d" % i, "shard": "%d/%d" % (i, shards), "exclude": excl, "phantom": "sim",
                  **HOSTED} for i in range(shards)]
        tasks += focus_tasks(ded)
        tasks += invivo_tasks(list(specs))
        return tasks
    sl = list(slugs)
    # A changed R2′ generator invalidates every GRE-only combo it forms with the R2′-consuming
    # χ-sep methods (those combos live in the χ-sep methods' focus jobs).
    if any(stage_of(specs.get(s)) == "r2prime-generation" for s in sl):
        sl += [s for s, sp in specs.items() if stage_of(sp) == "chi-separation"
               and consumes_r2prime(sp) and not is_skipped(sp)]
    return focus_tasks(sl) + invivo_tasks(sl)


# ---------------------------------------------------------------------------------------------------
# Scope: what changed since the last completed scoring
# ---------------------------------------------------------------------------------------------------

def _git(*args: str, check: bool = True) -> str:
    r = subprocess.run(["git", *args], capture_output=True, text=True)
    if check and r.returncode:
        raise RuntimeError(f"git {' '.join(args)}: {r.stderr.strip()}")
    return r.stdout


def commit_exists(sha: str) -> bool:
    return bool(sha) and subprocess.run(["git", "cat-file", "-e", f"{sha}^{{commit}}"],
                                        capture_output=True).returncode == 0


def is_ancestor(a: str, b: str) -> bool:
    return subprocess.run(["git", "merge-base", "--is-ancestor", a, b], capture_output=True).returncode == 0


def changed_files(base: str, head: str) -> set[str]:
    """Files touched by the first-parent commits in base..head, skipping any commit whose message
    carries [skip score]. A merge commit contributes what it merged (diff vs its first parent)."""
    files: set[str] = set()
    for sha in _git("rev-list", "--first-parent", f"{base}..{head}").split():
        if SKIP_TOKEN in _git("log", "-1", "--format=%B", sha):
            continue
        files |= set(_git("diff", "--name-only", f"{sha}^", sha, check=False).split())
    return files


def _slug_relevant(root: Path, slug: str, files: set[str], base: str, head: str) -> bool:
    """Did this slug change in a way that can move a score? Any non-yml file → yes; algorithm.yml
    alone → compare base vs head with the scoring-cosmetic keys stripped (a new/removed/unparseable
    spec is relevant — fail safe)."""
    rel = {f.split("/", 2)[2] for f in files if f.startswith(f"algorithms/{slug}/") and f.count("/") >= 2}
    if any(f != "algorithm.yml" for f in rel):
        return True
    spec = f"algorithms/{slug}/algorithm.yml"
    def load(ref):
        try:
            d = yaml.safe_load(_git("show", f"{ref}:{spec}"))
            return d if isinstance(d, dict) else None
        except Exception:  # noqa: BLE001 — missing at that ref, or unparseable
            return None
    b, h = load(base), load(head)
    if b is None or h is None:
        return True
    strip = lambda d: {k: v for k, v in d.items() if k not in SCORE_COSMETIC}
    return strip(b) != strip(h)


def scope_from_files(root: Path, files: set[str], base: str, head: str) -> tuple[bool, list[str]]:
    full = any(FULL_TRIGGER.match(f) for f in files)
    cand = sorted({f.split("/")[1] for f in files
                   if f.startswith("algorithms/") and f.count("/") >= 2 and not f.split("/")[1].startswith("_")})
    slugs = [s for s in cand if (root / s / "algorithm.yml").exists()
             and _slug_relevant(root, s, files, base, head)]
    return full, slugs


def read_state(path: Path) -> dict:
    try:
        d = json.loads(path.read_text())
        return d if isinstance(d, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


# ---------------------------------------------------------------------------------------------------
# Subtract what a still-running score run already covers
# ---------------------------------------------------------------------------------------------------

def task_covered(task: dict, other_sha: str, head: str, files_between: set[str]) -> bool:
    """Is `task` (planned at `head`) already correctly handled by a run scoring `other_sha`? Only if
    nothing that feeds the task changed in other_sha..head: the scorer itself, and — for a focus /
    in-vivo task — its method's folder. A shard covers the whole hosted matrix, so any scored-path
    change at all (an algorithm, the scorer) breaks its coverage."""
    if task.get("id") == "manual-include":
        return False
    if any(FULL_TRIGGER.match(f) for f in files_between):
        return False
    if "shard" in task:
        return not any(f.startswith("algorithms/") for f in files_between)
    focus = task.get("focus")
    return not any(f.startswith(f"algorithms/{focus}/") for f in files_between)


def gh_api(path: str) -> dict | list:
    import urllib.request
    req = urllib.request.Request("https://api.github.com" + path,
                                 headers={"Authorization": "Bearer " + os.environ["GH_TOKEN"],
                                          "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


def in_progress_runs(repo: str, my_run: str) -> list[dict]:
    """Other in-progress score runs: [{'sha': head_sha, 'active': {task ids queued/running/succeeded}}].
    A task id is the first element of the matrix job name, `score (<id>, ...)`."""
    out = []
    try:
        runs = gh_api(f"/repos/{repo}/actions/workflows/score.yml/runs?status=in_progress&per_page=50")
    except Exception as e:  # noqa: BLE001 — no coverage info is only ever a missed optimisation
        print(f"::warning::could not list in-progress runs ({e}); planning without subtraction")
        return out
    for r in runs.get("workflow_runs", []):
        if str(r.get("id")) == str(my_run):
            continue
        active: set[str] = set()
        try:
            page = 1
            while True:
                jobs = gh_api(f"/repos/{repo}/actions/runs/{r['id']}/jobs?per_page=100&filter=latest&page={page}")
                for j in jobs.get("jobs", []):
                    m = re.match(r"score \((\S+?)[,)]", j.get("name", ""))
                    if not m:
                        continue
                    if j.get("status") in ("queued", "in_progress", "waiting", "pending") or j.get("conclusion") == "success":
                        active.add(m.group(1))
                if len(jobs.get("jobs", [])) < 100:
                    break
                page += 1
        except Exception as e:  # noqa: BLE001
            print(f"::warning::could not read jobs of run {r['id']} ({e}); treating it as covering nothing")
            active = set()
        out.append({"id": r["id"], "sha": r.get("head_sha", ""), "active": active})
    return out


def subtract_in_progress(tasks: list[dict], head: str, others: list[dict]) -> tuple[list[dict], list[str]]:
    keep, dropped = [], []
    for t in tasks:
        covered_by = None
        for o in others:
            if t["id"] in o["active"] and o["sha"] and commit_exists(o["sha"]) and is_ancestor(o["sha"], head):
                if task_covered(t, o["sha"], head, changed_files(o["sha"], head)):
                    covered_by = o
                    break
        if covered_by:
            dropped.append(f"{t['id']} (run {covered_by['id']} @ {covered_by['sha'][:9]})")
        else:
            keep.append(t)
    return keep, dropped


# ---------------------------------------------------------------------------------------------------

def decide(env: dict, root: Path, reg: dict, state: dict) -> dict:
    """The whole decision, as data. Pure given env/root/reg/state except for git (scope diffs)."""
    event, sha = env.get("EVENT", "push"), env["SHA"]
    scope_in, include = (env.get("SCOPE") or "auto").strip(), (env.get("INCLUDE") or "").strip()
    shards = int(env.get("SHARDS") or 12)
    include_manual = (env.get("INCLUDE_MANUAL") or "false").lower() == "true"
    explicit: set[str] = set()
    notes: list[str] = []

    if include:  # manual single-combo recovery — wins over everything
        full, slugs, base = False, [], sha
        notes.append(f"manual include: {include}")
    elif scope_in == "all":
        full, slugs, base = True, [], sha
    elif event == "workflow_dispatch" and scope_in != "auto":
        full, base = False, sha
        slugs = [s for s in re.split(r"[,\s]+", scope_in) if s]
        explicit = set(slugs)
    else:
        # Base = the last COMPLETED scoring; fall back to the push's previous head / HEAD~1 when
        # there is no state yet (or it points at a rewritten commit).
        base = state.get("scored_sha") or ""
        if not (commit_exists(base) and is_ancestor(base, sha)):
            before = env.get("BEFORE") or ""
            base = before if (commit_exists(before) and is_ancestor(before, sha)) else f"{sha}~1"
            notes.append(f"no usable scoring-state; diffing from {base}")
        files = changed_files(base, sha)
        full, slugs = scope_from_files(root, files, base, sha)
        # Carry forward what earlier runs planned but did not finish.
        if state.get("pending_full"):
            full = True
            notes.append("pending_full carried from a previous incomplete run")
        carried = [s for s in state.get("pending_slugs", []) if s not in slugs and (root / s / "algorithm.yml").exists()]
        if carried:
            notes.append(f"pending slugs carried: {', '.join(carried)}")
            slugs = sorted(set(slugs) | set(carried))
        if event == "workflow_dispatch" and not files and not full and not slugs:
            notes.append("scope=auto: nothing changed since the last completed scoring")

    tasks = plan_tasks(root, reg, full=full, slugs=slugs, include=include, shards=shards,
                       explicit=explicit, include_manual=include_manual)
    # Manual-tier work this run OWES but is not allowed to schedule. `scored_sha` will advance past
    # the change that made it due, so it must be remembered explicitly: merge folds it into the
    # state's `pending_manual`, and an include_manual / explicit dispatch plans it from there —
    # so "score the manual ones too" means only the ones that actually need it.
    planned = {t["id"] for t in tasks}
    would = plan_tasks(root, reg, full=full, slugs=slugs, include=include, shards=shards,
                       explicit=explicit, include_manual=True) if not include else []
    skipped_manual = [t["id"] for t in would if t["id"] not in planned]
    owed = [i for i in state.get("pending_manual", []) if i not in planned]
    if owed and (include_manual or explicit) and not include:
        cand = plan_tasks(root, reg, full=False, slugs=all_slugs(root), include_manual=True)
        extra = [t for t in cand if t["id"] in owed and (include_manual or t.get("focus") in explicit)]
        if extra:
            notes.append(f"pending manual tasks carried: {', '.join(t['id'] for t in extra)}")
            tasks += extra
    dropped: list[str] = []
    if tasks and os.environ.get("GH_TOKEN") and env.get("REPO"):
        others = in_progress_runs(env["REPO"], env.get("RUN_ID", ""))
        tasks, dropped = subtract_in_progress(tasks, sha, others)
    return {"full": full, "slugs": slugs, "base": base, "tasks": tasks, "dropped": dropped,
            "skipped_manual": skipped_manual, "notes": notes}


def main() -> None:
    env = {k: os.environ.get(k, "") for k in
           ("EVENT", "SHA", "BEFORE", "SCOPE", "INCLUDE", "SHARDS", "INCLUDE_MANUAL", "RUN_ID", "REPO")}
    root = Path(os.environ.get("QSMCI_ALGORITHMS_DIR") or (ROOT / "algorithms"))
    reg = json.load(open(ROOT / "scripts/datasets.json"))
    d = decide(env, root, reg, read_state(ROOT / STATE_PATH))
    for n in d["notes"]:
        print(f"::notice::{n}")
    for x in d["dropped"]:
        print(f"skipping {x}: already being scored at an up-to-date commit")
    print(f"scope: full={d['full']} slugs={d['slugs']} base={d['base'][:12]}")
    print(f"planned {len(d['tasks'])} task(s): {', '.join(t['id'] for t in d['tasks']) or '-'}")
    if d["skipped_manual"]:
        print(f"manual-tier tasks owed but not scheduled (recorded as pending_manual; dispatch with "
              f"include_manual=true or scope=<slug> to run them): {', '.join(d['skipped_manual'])}")
    with open(os.environ.get("GITHUB_OUTPUT", "/dev/stdout"), "a") as out:
        out.write(f"tasks={json.dumps(d['tasks'])}\n")
        out.write(f"full={'true' if d['full'] else 'false'}\n")
        out.write(f"slugs={json.dumps(d['slugs'])}\n")
        out.write(f"base={d['base']}\n")
        out.write(f"skipped_manual={json.dumps(d['skipped_manual'])}\n")


if __name__ == "__main__":
    main()
