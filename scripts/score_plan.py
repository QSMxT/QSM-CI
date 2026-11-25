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
                               Scheduled ONE AT A TIME (see "Self-hosted pool" below). A bfr /
                               unwrap+bfr method's job (iqfm) is split by total-field source like a
                               highmem-long dipole's (split_fieldmaps): f-<slug>-gt, f-<slug>-<map>.
Per-method `split: fieldmaps` (any tier, a dipole or bfr / unwrap+bfr method): split its focus job the
same way, for a method whose composed matrix outgrows its tier's cap (whqsm on hosted). On the hosted
tiers this is also automatic: a focus job estimated past TARGET_PART_HOURS from recorded runtimes is
split by total-field source and/or into ranges of its composed cells (size_focus, "Sizing focus jobs").
    highmem       highmem()    the runners in repository variable QSMCI_HIGHMEM_RUNNER, 720-min cap,
                               1 container. Dispatch-only (named in `scope`), in runs of their own,
                               capped at max_parallel. Variable unset: identical to (unset).
                               Focus jobs sized to LENT_MAX_HOURS ("Sizing lent-runner jobs").
    highmem-long  highmem()    the same lent runners for long CPU work (MoDIP, INR-QSM: per-subject
                               optimisations whose reference runs on a GPU). Job cap LENT_JOB_MINUTES
                               (under the lent runner's 13-h shutdown); `timeout_minutes:` stays the
                               per-run budget, and `jobs:` (default 1). Dispatch-only like highmem, and a run
                               carrying one is capped at ONE job at a time whatever max_parallel says,
                               so the other lent runner stays free for parity jobs (QSMCI_PARITY_RUNNER
                               is the same pool, and a self-hosted job queued 24 h is failed).
                               Variable unset: the manual tier (it cannot run on a hosted runner).
                               A highmem-long DIPOLE's focus job is split by total-field source from
                               the start (split_fieldmaps): f-<slug>-gt runs its isolated runs (default
                               + tuned) and the gt columns, and f-<slug>-<field map> runs that field
                               map's columns only (pipeline.py --fieldmaps, --mode composed). Each is
                               then sized to LENT_MAX_HOURS like any lent job (size_focus).
    manual | gpu  MANUAL       NEVER scheduled automatically (not on push, not by scope=all). Scored
                               only when a workflow_dispatch names the slug in `scope`, or with
                               include_manual=true. For methods whose CPU cost makes them infeasible
                               on the shared box (MoDIP ≈ 12 h per inversion, INR-QSM ≈ 17 h) — a
                               cap cannot fix that, and every automatic attempt burned a runner for
                               its whole cap and produced nothing. `gpu` also documents the
                               hardware requirement for when a GPU runner exists.
Per-method overrides, honoured on self-hosted/manual/highmem-long only (hosted tiers are hard-capped
by GitHub; highmem keeps its fixed 720 min):
    timeout_minutes: N   wall-clock cap for the job — AND the per-run budget on every tier (see
                         qsm_ci.containers.timeout_s; without it a single run is capped at the
                         contract's 2 h and killed with a timeout DNF past that)
    jobs: N              concurrent containers inside the job (default 4 on self-hosted; set 1 for a
                         method that already uses every core, so runs don't contend with each other)
    manual_phantoms: []  phantom ids this method is scored on ONLY when explicitly dispatched (e.g.
                         DECOMPOSE on the 5M-voxel ridani-3t-iso phantom exceeds 12 h; the smaller
                         phantoms stay automatic)

Self-hosted pool
----------------
QSM-CI has two private runners, shared with parity runs and PR evaluate jobs. Main's scoring of the
long self-hosted methods (iqfm, amp-pe-qsmrs: up to 12 h per task) used to hold BOTH for hours and
starve everything else. So every task routed to the SELFHOSTED labels (the self-hosted and the
manual/gpu tiers) is emitted separately as `selfhosted_tasks`, which score.yml runs in its own
`score-selfhosted` matrix job with `max-parallel: 1`; everything else (`hosted_tasks`: the hosted
tiers, and highmem with its own pool cap) keeps full parallelism in the `score` job. The cap is per
run: two overlapping score runs can each hold one runner (GitHub has no cross-run queue that does
not cancel pending jobs), but one run never takes both.

Environment (set by score.yml):
    EVENT, SHA, BEFORE, SCOPE, INCLUDE, SHARDS, INCLUDE_MANUAL, RUN_ID, REPO, GH_TOKEN (optional),
    QSMCI_HIGHMEM_RUNNER (optional, see highmem())
Outputs (GITHUB_OUTPUT): tasks=<json list> (every task: merge's scoring state), hosted_tasks /
    selfhosted_tasks=<json list> (the `score` / `score-selfhosted` job matrices, see split_pools),
    full=true|false, slugs=<json list>, base=<sha>, max_parallel=<n> (only when the run plans
    highmem tasks)
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
import score_fresh  # noqa: E402

STATE_PATH = "results/scoring-state.json"
# Paths whose change re-scores everything (the scorer / orchestration). Mirrors score.yml's `paths:`
# trigger list minus algorithms/**, which scopes to the touched slugs.
FULL_TRIGGER = re.compile(r"^(eval/|scripts/pipeline\.py|scripts/publish_volumes\.py|stages\.yml)")
SKIP_TOKEN = "[skip score]"
# algorithm.yml keys whose edit cannot move a score: the evaluate gate's cosmetic set plus the
# scheduling knobs this planner reads itself. `compose:` is NOT here — it changes the matrix.
# `timeout_minutes` is deliberately NOT here: it is also the per-RUN wall-clock budget
# (qsm_ci.containers.timeout_s), so raising it is exactly how a run that DNF'd on time gets a real
# score — which makes it outcome-changing, not scheduling-only.
# `field_strength` (a method trained for one B0) only REMOVES combos — on phantoms at another field
# strength — and the rows they leave behind are dropped at merge by scripts/prune_inapplicable.py, so
# declaring it needs no rescore. (Removing the declaration later does: dispatch scope=<the χ-sep
# methods> to score the combos it re-allows.)
SCORE_COSMETIC = COSMETIC_KEYS | {"runner", "jobs", "manual_phantoms", "split", "memory_gb",
                                  "smoke_box", "smoke_params", "ci_skip_reason", "field_strength"}

HOSTED = {"runs_on": "ubuntu-latest", "timeout": 360, "jobs": 2}
HOSTED_LARGE = {"runs_on": "ubuntu-latest", "timeout": 360, "jobs": 1}
SELFHOSTED = {"runs_on": ["self-hosted", "Linux", "X64"], "timeout": 360, "jobs": 4}
HIGHMEM_TIMEOUT = 720
LONG_TIMEOUT_MAX = 7200   # GitHub's job execution limit on self-hosted runners: 5 days
TIERS = {"": "hosted", "hosted": "hosted", "hosted-large": "hosted-large", "highmem": "highmem",
         "highmem-long": "highmem-long", "self-hosted": "self-hosted", "manual": "manual", "gpu": "manual"}
LENT_TIERS = ("highmem", "highmem-long")   # the QSMCI_HIGHMEM_RUNNER pool
# The lent runner is shut down 13 h after a job starts: f-inr-qsm-gt (score runs 43137514862,
# 44654877699, 45292298269) and f-inr-qsm-romeo-qsmrs (45292298269) each got "The runner has received
# a shutdown signal" 12 h 59 m 30 s in. That shutdown skips every `if: always()` step, so the job's
# finished rows were never uploaded (in 44654877699 both isolated INR-QSM runs, 10 h of work, were
# lost). So a lent job is capped by GitHub first, at LENT_JOB_MINUTES: a timed-out job is cancelled
# the ordinary way, its teardown and upload run, and merge publishes what it finished. And lent jobs
# are sized to LENT_MAX_HOURS from recorded runtimes (size_focus), leaving room for a slower runner
# (INR-QSM inversions took 5.1-5.3 h on 2026-11-20 and 7.0 h on 2026-11-24).
LENT_JOB_MINUTES = 720
LENT_MAX_HOURS = 8.0


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


def highmem() -> dict | None:
    """QSMCI_HIGHMEM_RUNNER: a runner label, or {"runs_on": <label(s)>, "max_parallel": <n>} (default 1).
    None while unset."""
    raw = (os.environ.get("QSMCI_HIGHMEM_RUNNER") or "").strip()
    if not raw:
        return None
    cfg = raw
    if raw.startswith("{"):
        try:
            cfg = json.loads(raw)
        except json.JSONDecodeError:
            cfg = None
    runs_on, max_parallel = (cfg.get("runs_on"), cfg.get("max_parallel", 1)) if isinstance(cfg, dict) else (cfg, 1)
    labels = [runs_on] if isinstance(runs_on, str) else runs_on
    if not (isinstance(labels, list) and labels
            and all(isinstance(x, str) and re.fullmatch(r"[^\s,'\"{}\[\]]+", x) for x in labels)
            and type(max_parallel) is int and max_parallel >= 1):
        raise ValueError('QSMCI_HIGHMEM_RUNNER must be a runner label or {"runs_on": <label or list>, '
                         f'"max_parallel": <n>}}, not {raw!r}')
    return {"runs_on": runs_on, "max_parallel": max_parallel}


def tier_of(spec: dict | None) -> str:
    r = _scalar((spec or {}).get("runner")) or ""
    tier = TIERS.get(str(r), "hosted")
    # highmem is the default tier until its runners are configured; highmem-long is manual then (a
    # multi-day job cannot run on a hosted runner)
    if tier in LENT_TIERS and highmem() is None:
        return "hosted" if tier == "highmem" else "manual"
    return tier


def route(spec: dict | None) -> dict:
    """Runner, cap and intra-job container count for a method's task."""
    tier = tier_of(spec)
    if tier == "highmem":   # timeout_minutes:/jobs: don't apply
        return {"runs_on": highmem()["runs_on"], "timeout": HIGHMEM_TIMEOUT, "jobs": 1}
    if tier == "highmem-long":
        t, j = (spec or {}).get("timeout_minutes"), (spec or {}).get("jobs")
        # timeout_minutes: stays the per-RUN budget (qsm_ci.containers.timeout_s); the JOB is capped
        # below the lent runner's 13-h shutdown (LENT_JOB_MINUTES)
        return {"runs_on": highmem()["runs_on"],
                "timeout": min(t, LONG_TIMEOUT_MAX, LENT_JOB_MINUTES) if isinstance(t, int) and t > 0
                else LENT_JOB_MINUTES,
                "jobs": j if isinstance(j, int) and j > 0 else 1}
    base = {"hosted": HOSTED, "hosted-large": HOSTED_LARGE, "self-hosted": SELFHOSTED,
            "manual": SELFHOSTED}[tier]
    out = dict(base)
    if tier in ("self-hosted", "manual"):
        for key, field in (("timeout", "timeout_minutes"), ("jobs", "jobs")):
            v = (spec or {}).get(field)
            if isinstance(v, int) and v > 0:
                out[key] = v
    return out


def on_selfhosted(task: dict) -> bool:
    """Does this task run on QSM-CI's own self-hosted runners (the self-hosted and manual/gpu
    tiers)? Those go to score.yml's `score-selfhosted` job, one at a time."""
    return task.get("runs_on") == SELFHOSTED["runs_on"]


def split_pools(tasks: list[dict]) -> tuple[list[dict], list[dict]]:
    """(hosted_tasks, selfhosted_tasks): the matrices of score.yml's `score` job (full parallelism;
    a highmem run's cap is max_parallel) and its `score-selfhosted` job (max-parallel: 1)."""
    return [t for t in tasks if not on_selfhosted(t)], [t for t in tasks if on_selfhosted(t)]


def stage_of(spec: dict | None) -> str | None:
    s = (spec or {}).get("stage")
    return str(_scalar(s)) if s is not None else None


def is_skipped(spec: dict | None) -> bool:
    """Never scored: `ci_skip` (parked) or `parity_only` (an original kept only as the reference of
    a port parity pair, docs/parity.md)."""
    return spec is None or bool(spec.get("ci_skip")) or bool(spec.get("parity_only"))


def is_chisep(spec) -> bool:
    return stage_of(spec) in ("chi-separation", "r2prime-generation")


def is_dipole(spec) -> bool:
    return stage_of(spec) == "dipole"


def consumes_r2prime(spec) -> bool:
    inp = (spec or {}).get("inputs")
    return "r2prime" in [str(_scalar(a)) for a in inp] if isinstance(inp, list) else True


# Stages whose focus job composes ONE local field with every dipole: a self-hosted one is split too.
LOCALFIELD_STAGES = ("bfr", "unwrap+bfr")


def split_fieldmaps(spec, specs: dict) -> list[str] | None:
    """The total-field sources a focus job is split into, "gt" first: its `compose: fieldmaps:`
    list, or "gt" + every scored field-mapping method when it declares none. Split: a highmem-long
    dipole, and a self-hosted bfr / unwrap+bfr method. The latter composes with the whole dipole set
    (~40 methods, HEIDI at ~2.5 h a run) for every total-field source: iqfm's single focus job grew
    to 11-12 h and hit its 720-min cap (score runs 42448576786, 42801864615, 44225121850), losing all
    of it. One part per source is ~2-3 h. Any other dipole / bfr / unwrap+bfr method opts in with
    `split: fieldmaps` in its algorithm.yml, on any tier: whqsm (hosted, 2 containers) runs ~13 min a
    cell, so its 108-cell job needs ~12 h and was capped at 6 h after 28 cells (score run
    44438127054); split, each of its 6 parts is ~2.5 h. None = not split (any other tier or stage).
    Keyed on the DECLARED runner, so the split holds while highmem-long falls back to manual."""
    runner = str(_scalar((spec or {}).get("runner")) or "")
    opted = str(_scalar((spec or {}).get("split")) or "") == "fieldmaps" and (
        is_dipole(spec) or stage_of(spec) in LOCALFIELD_STAGES)
    if not (opted or (runner == "highmem-long" and is_dipole(spec))
            or (runner == "self-hosted" and stage_of(spec) in LOCALFIELD_STAGES)):
        return None
    c = (spec or {}).get("compose")
    fm = c.get("fieldmaps") if isinstance(c, dict) else None
    if not isinstance(fm, list) or not fm:
        fm = ["gt"] + sorted(s for s, sp in specs.items() if stage_of(sp) == "field-mapping" and not is_skipped(sp))
    fm = [str(f) for f in fm]
    return ["gt"] + [f for f in fm if f != "gt"]


def manual_phantoms(spec) -> set[str]:
    v = (spec or {}).get("manual_phantoms")
    return {str(_scalar(x)) for x in v} if isinstance(v, list) else set()


# ---------------------------------------------------------------------------------------------------
# Sizing lent-runner jobs (highmem, highmem-long): the same split, to LENT_MAX_HOURS (8 h)
# ---------------------------------------------------------------------------------------------------
# The lent runner is shut down 13 h into a job (see LENT_JOB_MINUTES), and INR-QSM's gt job alone
# (isolated default + tuned + 2 gt cells, ~5-7 h per inversion) could never finish. size_focus sizes
# lent focus jobs like hosted ones but to LENT_MAX_HOURS, with one container (jobs: 1) and each cell
# costed from the method's composed rows where it has them (closer than its isolated runtime on a
# runner it has to itself: MoDIP 2.9 h isolated, 1.3 h a cell). When the isolated runs do not fit
# beside any cells they get a job of their own (f-<slug>-iso), or one per variant when the pair is
# too long (f-<slug>-iso-default, -iso-tuned; pipeline.py --variants), and the cells are ranged as
# f-<slug>-<source>-p<k>of<n>. An in-vivo job too long for one part is split by variant the same way.
# Every lent job resumes (pipeline.py --resume), and a job whose every row is already scored and fresh
# is not scheduled at all (settle_fresh), so a re-dispatch after a cut-off run runs only what is owed.
# A part's `replaces` lists every coarser id it was cut from (f-inr-qsm, f-inr-qsm-gt), so the older
# pending_manual entries clear once all their parts are done, across runs (score_state).

# ---------------------------------------------------------------------------------------------------
# Sizing focus jobs: split one that would outrun GitHub's 6-h hosted cap
# ---------------------------------------------------------------------------------------------------
# A QSM.rs release repins many *-qsmrs methods at once, and each changed method gets one focus job
# scoring every composed cell it is part of. On push run 44991702275 (2026-11-22) 24 of those hit the
# 6-h cap: a field-mapping method has ~770 cells (45-60 container-hours), a bfr ~250, a dipole ~110
# behind 2.5-3.4 h of field maps and local fields computed first. A capped job is re-planned from cell
# 0 by the next run, so they never finished. Now the planner estimates each focus job from the
# runtimes results/index.json records and, on the hosted tiers, splits one that would run longer
# than TARGET_PART_HOURS:
#   1. a dipole / bfr / span method with more than one total-field source: one part per source
#      (f-<slug>-<source>, pipeline.py --fieldmaps; the same split as `split: fieldmaps`), so each
#      part computes one field map and its local fields;
#   2. any part still too long: n contiguous ranges of its composed cells (f-<id>-p<k>of<n>,
#      pipeline.py --cells k-1/n), n the fewest whose longest range fits.
# The isolated runs stay with the first part. Ids carry n, so another run's differently split parts
# never count as covering these (subtract_in_progress). Estimates use each stage's isolated runtime
# on the sim phantom (a composed row's runtime_s is the whole pipeline's, upstream included; the
# field map and local field are computed once per job, not once per cell) and DEFAULT_RUN_S for a
# method with none. On the 2.5-5 h focus jobs that finished in run 44991702275 it was 8-55 % high
# (it ignores the overlap of a job's two containers), so a part estimated at 3-4 h is well under 6.
TARGET_PART_HOURS = 3.0
PART_HOURS_STEPS = (TARGET_PART_HOURS, 4.0, 5.0)   # raised only to keep the matrix within MATRIX_MAX
DEFAULT_RUN_S = 600.0
SPLIT_TIERS = ("hosted", "hosted-large")   # the 6-h ones; self-hosted / lent tiers keep their caps
MATRIX_MAX = 256           # GitHub's limit on jobs one matrix generates
# Hosted jobs this run's `score` matrix runs at once. The organisation runs at most 60 hosted jobs at
# a time across every workflow; a release's score run used to take all of them for hours, starving
# PR CI, pages and parity. The rest of the matrix waits in the run (not in the runner queue, so
# GitHub's 24-h queue limit does not apply).
HOSTED_MAX_PARALLEL = 48
QSM_STAGES = ("field-mapping", "bfr", "unwrap+bfr", "dipole", "bfr+dipole", "end-to-end", "pipeline")
SPAN_STAGES = ("bfr+dipole", "end-to-end", "pipeline")


def stage_costs(runs: list[dict]) -> dict[str, dict[str, float]]:
    """{slug: {variant: seconds}}: each method's recorded isolated runtime on the sim phantom, plus
    "composed": the median time its own stage took in its composed rows (the row's whole-pipeline
    runtime_s less its field map's and local field's isolated runtimes), and "invivo-<variant>": its
    isolated runtimes on the in-vivo track. A method with no isolated sim runtime (INR-QSM: its
    isolated rows are DNFs from capped jobs) is costed from "composed" (see _cost)."""
    out: dict[str, dict[str, float]] = {}
    for r in runs:
        if (r.get("mode") != "isolated" or r.get("inputs") not in (None, "gt") or not r.get("runtime_s")
                or not r.get("slug")):
            continue
        if r.get("track") == "sim" and r.get("phantom") in (None, "sim"):
            out.setdefault(r["slug"], {})[r.get("variant") or "default"] = float(r["runtime_s"])
        elif r.get("track") == "invivo":
            out.setdefault(r["slug"], {})["invivo-" + (r.get("variant") or "default")] = float(r["runtime_s"])
    nets: dict[str, list[float]] = {}
    for r in runs:
        combo = r.get("combo") or {}
        if (r.get("track") != "sim" or r.get("mode") != "composed" or r.get("phantom") not in (None, "sim")
                or r.get("status") != "ok" or not r.get("runtime_s") or not combo):
            continue
        last = combo.get("dipole") or r.get("slug")
        if not last or "+" in str(last):
            continue
        up = [v for k, v in combo.items() if k in ("field_mapping", "bfr") and v and v != "gt"]
        nets.setdefault(last, []).append(
            float(r["runtime_s"]) - sum(out.get(u, {}).get("default", 0.0) for u in up))
    for slug, xs in nets.items():
        xs = sorted(x for x in xs if x > 0)
        if xs:
            out.setdefault(slug, {})["composed"] = xs[len(xs) // 2]
    return out


def _cost(costs: dict, slug: str, variant: str = "default", composed: bool = False) -> float:
    """Seconds one run of `slug` takes: its recorded isolated runtime (a cell's last stage prefers its
    composed-row time when `composed`, as on the lent runners, where one container runs alone and that
    is the closer measure: MoDIP 2.9 h isolated, 1.3 h per cell), else its composed-row time, else
    DEFAULT_RUN_S. A tuned variant with no recorded runtime costs what the default does."""
    c = costs.get(slug, {})
    if composed and "composed" in c:
        return c["composed"]
    if variant in c:
        return c[variant]
    if variant == "tuned" and "default" in c:
        return c["default"]
    return c.get("composed", DEFAULT_RUN_S)


def has_tuned(spec, dataset: str = "sim") -> bool:
    """Does the method declare tuned parameters for this dataset (pipeline._tuned_overrides: a
    per-dataset map, or a legacy scalar for sim)? Then its isolated job runs a tuned variant too."""
    for p in (spec or {}).get("parameters") or []:
        if isinstance(p, dict) and "tuned" in p:
            t = p["tuned"]
            if (isinstance(t, dict) and t.get(dataset) is not None) or (not isinstance(t, dict) and dataset == "sim"):
                return True
    return False


def iso_variants_of(spec, costs: dict, slug: str, dataset: str = "sim") -> list[str]:
    """The isolated variants a focus job runs: default, and tuned when declared (or recorded)."""
    key = "tuned" if dataset == "sim" else f"{dataset}-tuned"
    return ["default"] + (["tuned"] if has_tuned(spec, dataset) or key in costs.get(slug, {}) else [])


def iso_unit_ids(slug: str, variants, track: str = "sim") -> list[str]:
    """Row ids of a method's isolated runs on the track's default phantom (pipeline.iso_run_id)."""
    sfx = "" if track == "sim" else f"-{track}"
    return [f"{slug}-iso{'' if v == 'default' else '-tuned'}{sfx}" for v in variants]


def cell_unit_id(cell: tuple) -> str:
    """pipeline.cell_id on the default phantom."""
    return f"{cell[1]}~{cell[2]}~{cell[3]}-cmp" if cell[0] == "cell" else f"{cell[1]}~{cell[2]}-cmp"


def _consumes_totalfield(spec) -> bool:
    inp = (spec or {}).get("inputs")
    opt = (spec or {}).get("optional_inputs") or []
    names = [str(_scalar(a)) for a in inp] if isinstance(inp, list) and inp else \
        (["totalfield"] if stage_of(spec) in ("bfr", "bfr+dipole") else [])
    return "totalfield" in names + [str(_scalar(a)) for a in opt]


def focus_cells(specs: dict, focus: str, exclude=(), fieldmaps=None) -> tuple[list, list, list]:
    """(sources, cells, end-to-end spans) of a sim-phantom focus job, mirroring pipeline.plan_composed
    (a test holds the two together on the real algorithms/): cells are ("cell", source, bfr, dipole)
    column-major, then ("span", source, span), the order pipeline.py --cells splits."""
    exclude = set(exclude)
    live = {s: sp for s, sp in specs.items() if not is_skipped(sp) and s not in exclude and stage_of(sp)}
    by = lambda *st: sorted(s for s, sp in live.items() if stage_of(sp) in st)  # noqa: E731
    fm, bfr, dip = by("field-mapping"), by(*LOCALFIELD_STAGES), by("dipole")
    spans = by(*SPAN_STAGES)
    tf_spans = [s for s in spans if _consumes_totalfield(live[s])]
    e2e = [s for s in spans if s not in tf_spans]
    f = live.get(focus)
    st = stage_of(f)
    if f is None or is_chisep(f) or st not in QSM_STAGES:
        return [], [], []
    if st == "dipole":
        dip, tf_spans, e2e = [focus], [], []
        c = f.get("compose") if isinstance(f.get("compose"), dict) else {}
        if isinstance(c.get("bfrs"), list):
            bfr = [b for b in bfr if b in c["bfrs"]]
        if isinstance(c.get("fieldmaps"), list):
            fm = [m for m in fm if m in c["fieldmaps"]]
    elif st in LOCALFIELD_STAGES:
        bfr, tf_spans, e2e = [focus], [], []
    elif st == "field-mapping":
        fm, tf_spans, e2e = [focus], [], []
        fieldmaps = {focus} if fieldmaps is None else set(fieldmaps) - {"gt"}
    else:
        bfr, dip = [], []
        fm = fm if focus in tf_spans else []
        tf_spans, e2e = [x for x in tf_spans if x == focus], [x for x in e2e if x == focus]
    if fieldmaps is not None:
        fm = [m for m in fm if m in fieldmaps]
        if "gt" not in fieldmaps:
            e2e = []
    sources = (["gt"] if fieldmaps is None or "gt" in fieldmaps else []) + fm

    def composes(d, tfk, b):
        c = live[d].get("compose") if isinstance(live[d].get("compose"), dict) else {}
        return tfk in (c.get("fieldmaps") or [tfk]) and b in (c.get("bfrs") or [b])
    cells = [("cell", tfk, b, d) for tfk in sources for b in bfr for d in dip if composes(d, tfk, b)]
    cells += [("span", tfk, x) for tfk in sources for x in tf_spans]
    return sources, cells, e2e


def cell_range(n_cells: int, k: int, n: int) -> range:
    """pipeline.cell_range: part k of n contiguous, near-equal ranges."""
    return range(k * n_cells // n, (k + 1) * n_cells // n)


def part_seconds(cells: list, costs: dict, iso: str | None = None, e2e=(), variants=None,
                 composed: bool = False) -> float:
    """Container-seconds of a part: each field map and each local field it needs once, each cell's
    last stage, the end-to-end spans and (`iso`) the focus method's isolated runs: `variants` (default
    + any recorded tuned when None). `composed`: cost each cell's last stage from its composed rows."""
    c = lambda s: _cost(costs, s)  # noqa: E731
    fms = {x[1] for x in cells if x[1] != "gt"}
    cols = {(x[1], x[2]) for x in cells if x[0] == "cell"}
    total = sum(c(f) for f in fms) + sum(c(b) for _, b in cols)
    total += sum(_cost(costs, x[3] if x[0] == "cell" else x[2], composed=composed) for x in cells)
    total += sum(c(s) for s in e2e)
    if iso:
        if variants is None:
            variants = ["default"] + (["tuned"] if "tuned" in costs.get(iso, {}) else [])
        total += sum(_cost(costs, iso, v) for v in variants)
    return total


def parts_needed(cells: list, costs: dict, budget_s: float, iso: str | None, e2e=(), variants=None,
                 composed: bool = False) -> tuple[int, float]:
    """(n, longest part's container-seconds): the fewest contiguous cell ranges whose longest fits
    `budget_s`, the isolated runs and end-to-end spans riding with range 0."""
    for n in range(1, max(1, len(cells)) + 1):
        worst = max(part_seconds([cells[i] for i in cell_range(len(cells), k, n)], costs,
                                 iso if k == 0 else None, e2e if k == 0 else (), variants, composed)
                    for k in range(n))
        if worst <= budget_s:
            return n, worst
    return n, worst


def makespan_hours(hours: list[float], slots: int) -> float:
    """Wall-clock of jobs started in matrix order on `slots` runners, each as soon as one frees."""
    import heapq
    free = [0.0] * max(1, slots)
    for h in hours:
        heapq.heappush(free, heapq.heappop(free) + h)
    return max(free) if hours else 0.0


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


def input_levels(spec, reg: dict, ph: str) -> list[str]:
    """The degraded input levels (`input_levels` in scripts/datasets.json, e.g. ["l3"]) a method is
    also scored at on phantom `ph`: only χ-separation methods read the derived inputs, and only a
    dataset whose zip ships inputs-<level>/ lists the level."""
    if stage_of(spec) != "chi-separation":
        return []
    return [str(lv) for lv in (reg.get(ph, {}).get("input_levels") or [])]


# A full re-run's shard count, when none is given: enough shards that each has about this many hours
# of recorded runtime. GitHub stops a hosted job at 6 h; half that leaves room for uneven shards,
# setup, and runs with no recorded runtime yet (new methods, cells an earlier run never reached).
TARGET_SHARD_HOURS = 3.0
MIN_SHARDS, MAX_SHARDS = 24, 128


def sweep_hours(runs: list[dict], excluded: set[str]) -> float:
    """Container-hours the shard sweep costs, from the last recorded runtime of each run it scores:
    the sim-track runs that involve none of the `excluded` (dedicated) methods."""
    total = 0.0
    for r in runs:
        if r.get("track") != "sim" or not r.get("runtime_s"):
            continue
        parts = set((r.get("combo") or {}).values()) or set((r.get("slug") or "").split("+"))
        if parts & excluded:
            continue
        total += float(r["runtime_s"])
    return total / 3600


def auto_shards(hours: float) -> int:
    """Shards for `hours` of sweep work: each hosted shard runs HOSTED["jobs"] containers for about
    TARGET_SHARD_HOURS, within MIN_SHARDS..MAX_SHARDS. The sweep grows with every method added, so
    a fixed count stops fitting GitHub's 6-h cap (12 on 2026-11-01, 24 on 2026-11-05)."""
    import math
    need = math.ceil(hours / (HOSTED["jobs"] * TARGET_SHARD_HOURS))
    return max(MIN_SHARDS, min(MAX_SHARDS, need))


def load_runs(path: Path = ROOT / "results/index.json") -> list[dict]:
    try:
        return json.load(open(path)).get("runs") or []
    except (OSError, ValueError):
        return []


def dedicated(root: Path) -> list[str]:
    """Methods that run as their own focus job rather than inside the shard sweep: any non-hosted
    tier, or a χ-separation-track method (scored on separate phantoms)."""
    out = []
    for slug in all_slugs(root):
        spec = load_spec(root, slug)
        if tier_of(spec) != "hosted" or is_chisep(spec):
            out.append(slug)
    return out


def size_focus(t: dict, spec: dict | None, specs: dict, costs: dict | None,
               hours: float = TARGET_PART_HOURS, estimates: dict | None = None,
               units: dict | None = None) -> list[dict]:
    """A focus task as the job(s) that run it (see "Sizing focus jobs" and "Sizing lent-runner jobs").
    Without `costs`, or off the sized tiers, only split_fieldmaps' declared split applies. `estimates`
    collects each sized job's estimated wall-clock hours by id, `units` the row ids it scores (None
    when they cannot be listed), which the planner uses to leave a fully fresh lent part unscheduled."""
    forced = split_fieldmaps(spec, specs)
    tier = tier_of(spec)
    lent = tier in LENT_TIERS

    def by_source(g: str) -> dict:
        return {**t, "id": f"{t['id']}-{g}", "fieldmaps": g, "mode": "both" if g == "gt" else "composed",
                "replaces": t["id"]}
    if not (costs is not None and (tier in SPLIT_TIERS or lent) and t.get("phantom") == "sim"
            and stage_of(spec) in QSM_STAGES):
        return [by_source(g) for g in forced] if forced else [t]
    if lent:
        hours = LENT_MAX_HOURS
    focus = t["focus"]
    jobs = t.get("jobs") or 1
    budget = hours * 3600 * jobs
    sources, cells, e2e = focus_cells(specs, focus, (t.get("exclude") or "").split(","))
    variants = iso_variants_of(spec, costs, focus)
    groups = forced
    if (not groups and len(sources) > 1 and stage_of(spec) != "field-mapping"
            and part_seconds(cells, costs, focus, e2e, variants, lent) > budget):
        groups = sources
    out = []

    def emit(job: dict, gcells: list, iso_vs, ge2e) -> None:
        out.append(job)
        secs = part_seconds(gcells, costs, focus if iso_vs else None, ge2e, iso_vs, lent)
        if estimates is not None:
            estimates[job["id"]] = secs / 3600 / jobs
        if units is not None:
            units[job["id"]] = None if ge2e else (iso_unit_ids(focus, iso_vs or []) + [cell_unit_id(c) for c in gcells])

    for g in groups or [None]:
        if g is None:
            base, gcells, ge2e, iso, rep = t, cells, e2e, True, t["id"]
        else:
            base, gcells = by_source(g), [c for c in cells if c[1] == g]
            ge2e, iso = (e2e, True) if g == "gt" else ((), False)
            rep = t["id"]
        vs = variants if iso else None
        n, worst = parts_needed(gcells, costs, budget, focus if iso else None, ge2e, vs, lent)
        if iso and worst > budget:
            # The isolated runs do not fit beside any cells (INR-QSM: ~5-7 h per inversion, default
            # and tuned): give them their own job, or one per variant, and range the cells without them.
            rep = t["id"] if g is None else f"{t['id']},{base['id']}"
            iso_job = {k: v for k, v in t.items() if k not in ("fieldmaps", "cells")}
            if len(vs) == 1 or sum(_cost(costs, focus, v) for v in vs) <= budget:
                emit({**iso_job, "id": f"{t['id']}-iso", "mode": "isolated", "replaces": rep}, [], vs, ())
            else:
                for v in vs:
                    emit({**iso_job, "id": f"{t['id']}-iso-{v}", "mode": "isolated", "variants": v,
                          "replaces": rep}, [], [v], ())
            if not gcells and not ge2e:
                continue
            n, _ = parts_needed(gcells, costs, budget, None, ge2e, None, lent)
            for k in range(n):
                rng = [gcells[i] for i in cell_range(len(gcells), k, n)]
                emit({**base, "id": f"{base['id']}-p{k + 1}of{n}", "cells": f"{k}/{n}", "mode": "composed",
                      "replaces": rep}, rng, None, ge2e if k == 0 else ())
            continue
        if n == 1:
            emit(base, gcells, vs if base.get("mode", "both") != "composed" else None, ge2e)
            continue
        if g is not None:
            rep = f"{t['id']},{base['id']}"
        for k in range(n):
            part = {**base, "id": f"{base['id']}-p{k + 1}of{n}", "cells": f"{k}/{n}", "replaces": rep}
            if k:
                part["mode"] = "composed"   # the isolated runs (and end-to-end spans) ride with part 1
            emit(part, [gcells[i] for i in cell_range(len(gcells), k, n)], vs if k == 0 else None,
                 ge2e if k == 0 else ())
    return out


def size_invivo(t: dict, spec: dict | None, costs: dict | None, estimates: dict | None = None,
                units: dict | None = None) -> list[dict]:
    """A lent-runner in-vivo task (isolated runs only): one job, or one per variant when together
    they would run past LENT_MAX_HOURS. Other tiers' in-vivo tasks are left as they are."""
    if costs is None or tier_of(spec) not in LENT_TIERS:
        return [t]
    s, jobs = t["focus"], t.get("jobs") or 1
    vs = iso_variants_of(spec, costs, s, "invivo")
    secs = {v: _cost(costs, s, "invivo-" + v) if ("invivo-" + v) in costs.get(s, {}) else
            _cost(costs, s, "invivo-default") if "invivo-default" in costs.get(s, {}) else _cost(costs, s, v)
            for v in vs}
    if len(vs) > 1 and sum(secs.values()) > LENT_MAX_HOURS * 3600 * jobs:
        out = [{**t, "id": f"{t['id']}-{v}", "variants": v, "replaces": t["id"]} for v in vs]
    else:
        out = [t]
    for j in out:
        jv = [j["variants"]] if j.get("variants") else vs
        if estimates is not None:
            estimates[j["id"]] = sum(secs[v] for v in jv) / 3600 / jobs
        if units is not None:
            units[j["id"]] = iso_unit_ids(s, jv, "invivo")
    return out


def plan_tasks(root: Path, reg: dict, *, full: bool, slugs: list[str], include: str = "",
               shards: int = 24, explicit: set[str] | None = None,
               include_manual: bool = False, include_highmem: bool = False,
               costs: dict | None = None, part_hours: float = TARGET_PART_HOURS, resume: bool = False,
               estimates: dict | None = None, units: dict | None = None) -> list[dict]:
    """The matrix for a run. `explicit` = slugs a human named on dispatch: they (and their manual
    phantoms) are planned even when their tier is manual or highmem. `include_manual` lifts that for
    the manual tier, `include_highmem` (internal) for highmem and highmem-long. `costs` (stage_costs)
    sizes the hosted focus jobs (size_focus; None = no automatic split), `part_hours` is the target
    length of one part (LENT_MAX_HOURS on the lent tiers), and `resume` marks the sim focus jobs to
    skip cells already scored and fresh (pipeline.py --resume; always on for the lent tiers).
    `estimates` / `units` collect each sized job's hours and row ids (size_focus)."""
    explicit = explicit or set()
    specs = {s: load_spec(root, s) for s in all_slugs(root)}

    def allowed(slug: str, ph: str | None = None) -> bool:
        spec = specs.get(slug)
        if is_skipped(spec):
            return False
        wanted = include_manual or slug in explicit
        if tier_of(spec) == "manual" and not wanted:
            return False
        if tier_of(spec) in LENT_TIERS and not (include_highmem or slug in explicit):
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
                if (resume or tier_of(spec) in LENT_TIERS) and ph == "sim" and stage_of(spec) in QSM_STAGES:
                    t["resume"] = "true"
                # One job, or one per total-field source / cell range (size_focus). A part's `replaces`
                # names the unsplit id, so an older pending_manual entry clears once all parts finish.
                parts = size_focus(t, spec, specs, costs, part_hours, estimates, units)
                tasks += parts
                if len(parts) > 1 or parts[0] is not t:
                    continue

                # Degraded inputs (pipeline.py --inputs <level>): a separate job per level, so it
                # never lengthens the ground-truth-input job. Like that job it runs the method's
                # isolated run and, for an R2′-consuming method, its GRE-only grid at the level
                # (every generator × it, mode both); a GRE-native method has no grid, so its level
                # job stays isolated. No tuned pass at a degraded level, so the level job is the
                # ground-truth job minus the tuned run and fits the same cap.
                for lv in input_levels(spec, reg, ph):
                    lt = {"id": t["id"] + "-" + lv, "focus": s, "phantom": ph, "inputs": lv, **route(spec)}
                    if not consumes_r2prime(spec):
                        lt["mode"] = "isolated"
                    tasks.append(lt)
        return tasks

    def invivo_tasks(sl: list[str]) -> list[dict]:
        out = []
        for s in sorted(set(sl)):
            if not (s in specs and is_dipole(specs[s]) and allowed(s)):
                continue
            t = {"id": "iv-" + s, "focus": s, "phantom": "invivo", "track": "invivo", **route(specs[s])}
            if tier_of(specs[s]) in LENT_TIERS:
                t["resume"] = "true"   # a re-dispatch skips the in-vivo runs a cut-off job published
            out += size_invivo(t, specs[s], costs, estimates, units)
        return out

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
    # χ-sep methods, at every input level (those combos live in the χ-sep methods' focus jobs and
    # their degraded-input jobs), so all of those jobs are re-planned.
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
    """Other in-progress score runs: [{'sha': head_sha, 'active': {task keys queued/running/succeeded}}].
    A task's key is the first element of the matrix job name, `score (<id>, ...)` or
    `score-selfhosted (<id>, ...)`, and for a shard its slice too (`task_key`): `s06` of a 48-way
    split and `s06` of a 128-way split are different work."""
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
                    m = re.match(r"score(?:-selfhosted)? \((\S+?)(?:, (\d+/\d+))?[,)]", j.get("name", ""))
                    if not m:
                        continue
                    if j.get("status") in ("queued", "in_progress", "waiting", "pending") or j.get("conclusion") == "success":
                        active.add(task_key({"id": m.group(1), "shard": m.group(2)}))
                if len(jobs.get("jobs", [])) < 100:
                    break
                page += 1
        except Exception as e:  # noqa: BLE001
            print(f"::warning::could not read jobs of run {r['id']} ({e}); treating it as covering nothing")
            active = set()
        out.append({"id": r["id"], "sha": r.get("head_sha", ""), "active": active})
    return out


def task_key(t: dict) -> str:
    """What identifies a task's work across runs: its id, and for a shard its slice (`s06@6/128`)."""
    return f"{t['id']}@{t['shard']}" if t.get("shard") else t["id"]


def subtract_in_progress(tasks: list[dict], head: str, others: list[dict]) -> tuple[list[dict], list[str]]:
    keep, dropped = [], []
    for t in tasks:
        covered_by = None
        for o in others:
            if task_key(t) in o["active"] and o["sha"] and commit_exists(o["sha"]) and is_ancestor(o["sha"], head):
                if task_covered(t, o["sha"], head, changed_files(o["sha"], head)):
                    covered_by = o
                    break
        if covered_by:
            dropped.append(f"{t['id']} (run {covered_by['id']} @ {covered_by['sha'][:9]})")
        else:
            keep.append(t)
    return keep, dropped


def settle_fresh(tasks: list[dict], units: dict, on_lent, is_fresh) -> tuple[list[dict], list[dict]]:
    """(to run, settled): a lent-runner job whose every row (units[id]) is already scored and fresh is
    not scheduled. It goes into the run's scoring state as done (`settled`), so the pending_manual
    entries it stands for are paid off like a finished job's (score_state.done_ids)."""
    keep, settled = [], []
    for t in tasks:
        if on_lent(t) and is_fresh(units.get(t["id"])):
            settled.append({**t, "settled": "fresh"})
        else:
            keep.append(t)
    return keep, settled


# ---------------------------------------------------------------------------------------------------

def decide(env: dict, root: Path, reg: dict, state: dict, runs: "list[dict] | None" = None,
           fresh: "set[str] | None" = None) -> dict:
    """The whole decision, as data. Pure given env/root/reg/state except for git (scope diffs).
    `runs` (results/index.json's, read when None) sizes a full re-run when SHARDS is empty or
    `auto`. `fresh` (row ids a re-run would only reproduce; score_fresh.fresh_ids over `runs` at SHA
    when None) settles the lent-runner jobs whose every run is already scored (settle_fresh)."""
    event, sha = env.get("EVENT", "push"), env["SHA"]
    scope_in, include = (env.get("SCOPE") or "auto").strip(), (env.get("INCLUDE") or "").strip()
    shards_in = (env.get("SHARDS") or "auto").strip().lower()
    include_manual = (env.get("INCLUDE_MANUAL") or "false").lower() == "true"
    explicit: set[str] = set()
    notes: list[str] = []
    resume = False

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
        # An automatic run's focus jobs skip what an earlier run already published at an up-to-date
        # commit (pipeline.py --resume). A dispatch naming slugs, or scope=all, rescores everything.
        resume = True

    if runs is None:
        runs = load_runs()
    costs = stage_costs(runs)
    if shards_in != "auto":
        shards = int(shards_in)
    elif full and not include:
        hours = sweep_hours(runs, set(dedicated(root)))
        shards = auto_shards(hours)
        notes.append(f"{shards} shards for about {hours:.0f} container-hours of recorded sweep runtime "
                     f"({HOSTED['jobs']} containers per shard, about {TARGET_SHARD_HOURS:g} h each)")
    else:
        shards = MIN_SHARDS
    # Size the focus jobs to TARGET_PART_HOURS; only if that outgrows one matrix, allow longer parts.
    units: dict[str, "list[str] | None"] = {}
    for part_hours in PART_HOURS_STEPS:
        estimates: dict[str, float] = {}
        tasks = plan_tasks(root, reg, full=full, slugs=slugs, include=include, shards=shards,
                           explicit=explicit, include_manual=include_manual, costs=costs,
                           part_hours=part_hours, resume=resume, estimates=estimates, units=units)
        if len(split_pools(tasks)[0]) <= MATRIX_MAX:
            break
    if part_hours != TARGET_PART_HOURS:
        notes.append(f"focus jobs sized to {part_hours:g} h (not {TARGET_PART_HOURS:g} h) to keep the "
                     f"matrix within GitHub's {MATRIX_MAX} jobs")
    on_lent = lambda t: bool(t.get("focus")) and tier_of(load_spec(root, t["focus"])) in LENT_TIERS  # noqa: E731
    hosted_est = {t["id"]: estimates[t["id"]] for t in split_pools(tasks)[0]
                  if t["id"] in estimates and not on_lent(t)}
    if hosted_est:
        longest = max(hosted_est, key=hosted_est.get)
        notes.append(f"{len(hosted_est)} sized focus job(s), longest {longest} at about "
                     f"{hosted_est[longest]:.1f} h; together about "
                     f"{makespan_hours(list(hosted_est.values()), HOSTED_MAX_PARALLEL):.1f} h "
                     f"on {HOSTED_MAX_PARALLEL} hosted runners (estimated from recorded runtimes)")
    # Manual-tier work this run OWES but is not allowed to schedule. `scored_sha` will advance past
    # the change that made it due, so it must be remembered explicitly: merge folds it into the
    # state's `pending_manual`, and an include_manual / explicit dispatch plans it from there —
    # so "score the manual ones too" means only the ones that actually need it.
    planned = {t["id"] for t in tasks}
    would = plan_tasks(root, reg, full=full, slugs=slugs, include=include, shards=shards,
                       explicit=explicit, include_manual=True, include_highmem=True, costs=costs,
                       part_hours=part_hours, units=units) if not include else []

    # Lent-runner jobs whose every run is already scored and fresh are not run again (nor owed).
    fresh_cache: list = []

    def is_fresh(ids) -> bool:
        if not fresh_cache:
            fresh_cache.append(fresh if fresh is not None else
                               score_fresh.fresh_ids(runs, sha, modes=("composed", "isolated")))
        return bool(ids) and all(i in fresh_cache[0] for i in ids)
    would, _ = settle_fresh(would, units, on_lent, is_fresh)
    skipped_manual = [t["id"] for t in would if t["id"] not in planned]
    owed = [i for i in state.get("pending_manual", []) if i not in planned]
    if owed and (include_manual or explicit) and not include:
        cand = plan_tasks(root, reg, full=False, slugs=all_slugs(root), include_manual=True, include_highmem=True,
                          costs=costs, part_hours=part_hours, units=units)
        extra = [t for t in cand if t["id"] in owed
                 and (t.get("focus") in explicit or (include_manual and not on_lent(t)))]
        if extra:
            notes.append(f"pending manual tasks carried: {', '.join(t['id'] for t in extra)}")
            tasks += extra
    tasks, settled = settle_fresh(tasks, units, on_lent, is_fresh)
    if settled:
        notes.append(f"already scored at an up-to-date commit, not run again: {', '.join(t['id'] for t in settled)}")
    lent_est = {t["id"]: estimates[t["id"]] for t in tasks if on_lent(t) and t["id"] in estimates}
    if lent_est:
        longest = max(lent_est, key=lent_est.get)
        notes.append(f"{len(lent_est)} lent-runner job(s) sized to {LENT_MAX_HOURS:g} h, longest {longest} at about "
                     f"{lent_est[longest]:.1f} h; together about {sum(lent_est.values()):.1f} h one after another "
                     f"(estimated from recorded runtimes; each job capped at {LENT_JOB_MINUTES // 60} h)")
    dropped: list[str] = []
    if tasks and os.environ.get("GH_TOKEN") and env.get("REPO"):
        others = in_progress_runs(env["REPO"], env.get("RUN_ID", ""))
        tasks, dropped = subtract_in_progress(tasks, sha, others)
    # max-parallel caps the whole matrix, so a highmem run carries highmem tasks only
    max_parallel = None
    lent = [t["id"] for t in tasks if on_lent(t)]
    if lent:
        rest = [t["id"] for t in tasks if not on_lent(t)]
        if rest:
            hm = sorted({t["focus"] for t in tasks if on_lent(t)})
            raise ValueError(f"dispatch highmem methods on their own: scope={','.join(hm)}, and the rest in "
                             f"another run (this one also planned {', '.join(rest)})")
        max_parallel = highmem()["max_parallel"]
        # a multi-day job holds its runner for days: never more than one, so parity keeps the other
        if any(tier_of(load_spec(root, t["focus"])) == "highmem-long" for t in tasks if on_lent(t)):
            max_parallel = 1
    return {"full": full, "slugs": slugs, "base": base, "tasks": tasks, "dropped": dropped,
            "skipped_manual": skipped_manual, "notes": notes, "max_parallel": max_parallel,
            "estimates": {i: h for i, h in estimates.items() if i in {t["id"] for t in tasks}},
            "part_hours": part_hours, "settled": settled}


def main() -> None:
    env = {k: os.environ.get(k, "") for k in
           ("EVENT", "SHA", "BEFORE", "SCOPE", "INCLUDE", "SHARDS", "INCLUDE_MANUAL", "RUN_ID", "REPO")}
    root = Path(os.environ.get("QSMCI_ALGORITHMS_DIR") or (ROOT / "algorithms"))
    reg = json.load(open(ROOT / "scripts/datasets.json"))
    try:
        d = decide(env, root, reg, read_state(ROOT / STATE_PATH))
    except ValueError as e:   # a mixed highmem dispatch, or a malformed QSMCI_HIGHMEM_RUNNER
        print(f"::error::{e}")
        sys.exit(1)
    for n in d["notes"]:
        print(f"::notice::{n}")
    for x in d["dropped"]:
        print(f"skipping {x}: already being scored at an up-to-date commit")
    print(f"scope: full={d['full']} slugs={d['slugs']} base={d['base'][:12]}")
    print(f"planned {len(d['tasks'])} task(s): {', '.join(t['id'] for t in d['tasks']) or '-'}")
    hosted, selfhosted = split_pools(d["tasks"])
    if selfhosted:
        print(f"self-hosted, one at a time: {', '.join(t['id'] for t in selfhosted)}")
    if d["max_parallel"]:
        print(f"highmem run: at most {d['max_parallel']} job(s) at a time on the lent runners")
    if d["skipped_manual"]:
        print(f"manual/highmem-tier tasks owed but not scheduled (recorded as pending_manual; dispatch "
              f"with include_manual=true or scope=<slug> to run them, highmem ones only by scope=<slug>): "
              f"{', '.join(d['skipped_manual'])}")
    with open(os.environ.get("GITHUB_OUTPUT", "/dev/stdout"), "a") as out:
        # merge's scoring state also gets the settled (fresh, unscheduled) jobs, counted as done
        out.write(f"tasks={json.dumps(d['tasks'] + d['settled'])}\n")
        out.write(f"hosted_tasks={json.dumps(hosted)}\n")
        out.write(f"selfhosted_tasks={json.dumps(selfhosted)}\n")
        out.write(f"full={'true' if d['full'] else 'false'}\n")
        out.write(f"slugs={json.dumps(d['slugs'])}\n")
        out.write(f"base={d['base']}\n")
        out.write(f"skipped_manual={json.dumps(d['skipped_manual'])}\n")
        # highmem runs: the lent pool's cap; any other run: HOSTED_MAX_PARALLEL of the org's 60
        out.write(f"max_parallel={d['max_parallel'] or HOSTED_MAX_PARALLEL}\n")


if __name__ == "__main__":
    main()
