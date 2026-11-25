"""score_plan.size_focus + pipeline.py --cells / --resume: a focus job too long for GitHub's 6-h hosted
cap is split into parts sized from recorded runtimes, and a re-planned part resumes.

Push run 44991702275 (2026-11-22, a QSM.rs release repinning 25 *-qsmrs methods) planned one focus
job per method; 24 hit the cap and every re-plan restarted them from cell 0. These pin down:
  - the planner's cell enumeration is the scorer's (on the real algorithms/), so its estimates and
    the --cells ranges it asks for describe the cells pipeline.py actually runs;
  - a field-mapping focus job is sharded by cell range, a dipole / bfr one split by total-field
    source first, and each part's estimate fits the target;
  - the matrix stays within GitHub's limits and the org's hosted-job cap;
  - parts that abort keep their method pending; --cells parts partition the job; --resume only
    skips cells nothing changed under.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import threading
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("score_plan", ROOT / "scripts" / "score_plan.py")
sp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sp)
_spec = importlib.util.spec_from_file_location("score_state", ROOT / "scripts" / "score_state.py")
ss = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ss)

REG = {"sim": {"track": "sim", "active": True, "default": True},
       "invivo": {"track": "invivo", "active": True, "default": True}}


@pytest.fixture(scope="module")
def pipeline():
    import sys
    sys.path.insert(0, str(ROOT / "scripts"))
    import pipeline as p
    return p


def _algos(tmp_path: Path, specs: dict[str, str]) -> Path:
    root = tmp_path / "algorithms"
    for slug, body in specs.items():
        (root / slug).mkdir(parents=True)
        (root / slug / "algorithm.yml").write_text(body)
    return root


# A small matrix: 2 field maps, 3 bfrs, 4 dipoles (one heavy dedicated), a span.
MATRIX = {
    "romeo": "stage: field-mapping\nimage: x\n",
    "lap": "stage: field-mapping\nimage: x\n",
    **{b: "stage: bfr\nimage: x\n" for b in ("vsharp", "pdf", "lbv")},
    **{d: "stage: dipole\nimage: x\n" for d in ("tkd", "rts", "medi", "nltv")},
    "slowdip": "stage: dipole\nimage: x\nrunner: self-hosted\n",
    "tgv": "stage: bfr+dipole\nimage: x\n",
}
# Recorded isolated runtimes (s): medi is the slow dipole, the rest are quick.
RUNS = ([{"track": "sim", "mode": "isolated", "slug": s, "variant": "default", "runtime_s": rt}
         for s, rt in {"romeo": 60, "lap": 60, "vsharp": 120, "pdf": 120, "lbv": 120,
                       "tkd": 600, "rts": 600, "medi": 5400, "nltv": 3600, "tgv": 900}.items()]
        + [{"track": "sim", "mode": "isolated", "slug": "medi", "variant": "tuned", "runtime_s": 1800},
           {"track": "sim", "mode": "isolated", "slug": "tkd", "phantom": "other", "runtime_s": 1e6}])


def _plan(root, slugs, **kw):
    est = {}
    tasks = sp.plan_tasks(root, REG, full=False, slugs=slugs, costs=sp.stage_costs(RUNS), estimates=est, **kw)
    return {t["id"]: t for t in tasks}, est


# ------------------------------------------------------------------- the planner's view == the scorer's

def test_focus_cells_mirror_the_scorers_composed_matrix_on_the_real_algorithms(pipeline):
    """score_plan cannot import pipeline.py (the plan job installs only pyyaml), so it enumerates the
    cells itself. Hold the two together on every real method, with and without --fieldmaps."""
    specs = {s: sp.load_spec(ROOT / "algorithms", s) for s in sp.all_slugs(ROOT / "algorithms")}
    algos = pipeline.discover_algorithms("sim", "sim")
    heavy = {s for s in sp.dedicated(ROOT / "algorithms") if sp.is_dipole(specs[s])}
    checked = 0
    for a in algos:
        if a["stage"] not in sp.QSM_STAGES:
            continue
        excl = set() if a["stage"] == "dipole" else heavy
        live = [x for x in algos if x["slug"] not in excl]
        plan = pipeline.plan_composed(live, a["slug"], "sim", None, None)
        sources, cells, e2e = sp.focus_cells(specs, a["slug"], excl)
        assert cells == plan.cells, a["slug"]
        assert sources == plan.fm_keys and e2e == [s["slug"] for s in plan.e2e_spans], a["slug"]
        for src in sources[:2]:
            assert sp.focus_cells(specs, a["slug"], excl, {src})[1] == \
                pipeline.plan_composed(live, a["slug"], "sim", None, None, {src}).cells, (a["slug"], src)
        checked += 1
    assert checked > 50


def test_a_field_mapping_focus_no_longer_runs_the_ground_truth_columns(pipeline):
    algos = [{"slug": s, "stage": st, "produces": p, "consumes": c} for s, st, p, c in (
        ("romeo", "field-mapping", ["totalfield"], ["phase"]),
        ("vsharp", "bfr", ["localfield"], ["totalfield"]),
        ("tkd", "dipole", ["chimap"], ["localfield"]))]
    plan = pipeline.plan_composed(algos, "romeo", "sim", None, None)
    assert plan.fm_keys == ["romeo"] and plan.cells == [("cell", "romeo", "vsharp", "tkd")]


# ------------------------------------------------------------------------------------- splitting

def test_a_field_mapping_focus_is_sharded_into_cell_ranges_that_each_fit(tmp_path):
    root = _algos(tmp_path, MATRIX)
    t, est = _plan(root, ["lap"])
    parts = [i for i in t if i.startswith("f-lap-")]
    n = len(parts)
    assert n > 1 and parts == [f"f-lap-p{k + 1}of{n}" for k in range(n)]
    assert [t[i]["cells"] for i in parts] == [f"{k}/{n}" for k in range(n)]
    assert "mode" not in t[parts[0]] and all(t[i]["mode"] == "composed" for i in parts[1:])  # isolated: part 1
    assert all(t[i]["replaces"] == "f-lap" and "fieldmaps" not in t[i] for i in parts)
    assert all(est[i] <= sp.TARGET_PART_HOURS for i in parts)
    assert list(t[parts[0]])[:2] == ["id", "focus"]     # the job name still starts with the id
    # the n ranges cover the job's cells exactly once
    _, cells, _ = sp.focus_cells({s: sp.load_spec(root, s) for s in sp.all_slugs(root)}, "lap",
                                 t[parts[0]]["exclude"].split(","))
    covered = [i for k in range(n) for i in sp.cell_range(len(cells), k, n)]
    assert covered == list(range(len(cells)))
    # n is the fewest that fit: one fewer part would overrun
    assert max(sp.part_seconds([cells[i] for i in sp.cell_range(len(cells), k, n - 1)], sp.stage_costs(RUNS),
                               "lap" if k == 0 else None) for k in range(n - 1)) > sp.TARGET_PART_HOURS * 3600 * 2


def test_a_dipole_focus_is_split_by_field_source_then_by_cells_only_where_needed(tmp_path):
    root = _algos(tmp_path, MATRIX)
    t, est = _plan(root, ["medi", "tkd"])
    # medi: 3 sources × 3 bfrs × 1.5 h + its isolated runs — too long for one job, so one part per
    # source; the gt part also carries the isolated runs (default + tuned), so it alone is sharded
    medi = [i for i in t if i.startswith("f-medi-")]
    assert medi == ["f-medi-gt-p1of2", "f-medi-gt-p2of2", "f-medi-lap", "f-medi-romeo"]
    assert [t[i]["fieldmaps"] for i in medi] == ["gt", "gt", "lap", "romeo"]
    assert [t[i]["mode"] for i in medi] == ["both", "composed", "composed", "composed"]
    assert [t[i].get("cells") for i in medi] == ["0/2", "1/2", None, None]
    # a part of a field map's job pays off both the unsplit id and that field map's job id
    assert [t[i]["replaces"] for i in medi] == ["f-medi,f-medi-gt", "f-medi,f-medi-gt", "f-medi", "f-medi"]
    assert all(est[i] <= sp.TARGET_PART_HOURS for i in medi)
    # tkd: fits one job, so it stays whole (no split, no estimate overrun)
    assert "f-tkd" in t and "cells" not in t["f-tkd"] and est["f-tkd"] <= sp.TARGET_PART_HOURS
    assert "iv-medi" in t and "cells" not in t["iv-medi"]           # in-vivo is isolated-only
    # without recorded costs (and off the hosted tiers) nothing is split automatically
    plain = {x["id"] for x in sp.plan_tasks(root, REG, full=False, slugs=["medi", "lap"])}
    assert plain == {"f-medi", "iv-medi", "f-lap"}
    assert [x["id"] for x in sp.plan_tasks(root, REG, full=False, slugs=["slowdip"],
                                           costs=sp.stage_costs(RUNS))] == ["f-slowdip", "iv-slowdip"]


def test_a_declared_split_still_holds_and_is_sharded_further_if_needed(tmp_path):
    root = _algos(tmp_path, {**MATRIX, "medi": "stage: dipole\nimage: x\nsplit: fieldmaps\n"})
    t, _ = _plan(root, ["medi"])
    assert {t[i]["fieldmaps"] for i in t if i.startswith("f-medi")} == {"gt", "lap", "romeo"}


def test_resume_is_set_on_automatic_runs_only(tmp_path, monkeypatch):
    monkeypatch.delenv("GH_TOKEN", raising=False)
    root = _algos(tmp_path, MATRIX)
    t, _ = _plan(root, ["tkd"], resume=True)
    assert t["f-tkd"]["resume"] == "true" and "resume" not in t["iv-tkd"]
    d = sp.decide({"EVENT": "workflow_dispatch", "SHA": "HEAD", "SCOPE": "tkd"}, root, REG, {}, runs=RUNS)
    assert not any(x.get("resume") for x in d["tasks"])


def test_the_matrix_stays_within_githubs_limits(tmp_path, monkeypatch):
    """A matrix may generate at most 256 jobs, and the org runs 60 hosted jobs at once: the planner
    lengthens parts (never past PART_HOURS_STEPS' last step) rather than overflow the matrix, and
    the score job runs at most HOSTED_MAX_PARALLEL at a time."""
    monkeypatch.delenv("GH_TOKEN", raising=False)
    many = {f"d{i:03d}": "stage: dipole\nimage: x\n" for i in range(60)}
    root = _algos(tmp_path, {**MATRIX, **many})
    runs = RUNS + [{"track": "sim", "mode": "isolated", "slug": s, "variant": "default", "runtime_s": 8000}
                   for s in many]
    d = sp.decide({"EVENT": "workflow_dispatch", "SHA": "HEAD", "SCOPE": ",".join(many)}, root, REG, {},
                  runs=runs)
    hosted, _ = sp.split_pools(d["tasks"])
    assert len(hosted) <= sp.MATRIX_MAX and d["part_hours"] > sp.TARGET_PART_HOURS
    assert all(h <= d["part_hours"] for h in d["estimates"].values())
    assert any("to keep the matrix within" in n for n in d["notes"])
    assert sp.HOSTED_MAX_PARALLEL < 60
    assert sp.makespan_hours([3.0] * 96, sp.HOSTED_MAX_PARALLEL) == pytest.approx(6.0)
    assert sp.makespan_hours([], 48) == 0


def test_plan_writes_the_hosted_cap_for_ordinary_runs(tmp_path, monkeypatch):
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.delenv("QSMCI_HIGHMEM_RUNNER", raising=False)
    root = _algos(tmp_path, MATRIX)
    out = tmp_path / "out"
    env = {"EVENT": "workflow_dispatch", "SHA": "HEAD", "SCOPE": "tkd", "GITHUB_OUTPUT": str(out),
           "QSMCI_ALGORITHMS_DIR": str(root)}
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    sp.main()
    o = dict(line.split("=", 1) for line in out.read_text().splitlines())
    assert o["max_parallel"] == str(sp.HOSTED_MAX_PARALLEL)


# ----------------------------------------------------------------------------- pending bookkeeping

def test_a_split_methods_parts_keep_it_pending_until_every_part_finished(tmp_path):
    root = _algos(tmp_path, MATRIX)
    t, _ = _plan(root, ["lap", "tkd"])
    tasks = list(t.values())
    parts = [i for i in t if i.startswith("f-lap-")]
    always = lambda a, b: True  # noqa: E731
    # one part capped / cancelled: lap stays pending, tkd (done) clears, and the run's sha advances
    done = set(t) - {parts[1]}
    st = ss.update({"scored_sha": "a", "pending_slugs": ["lap", "tkd"]}, "b", tasks, done, ancestor=always, now="x")
    assert st["pending_slugs"] == ["lap"] and st["scored_sha"] == "b"
    # the next run re-plans every part; when all of them finish, lap clears
    st = ss.update(st, "c", tasks, set(t), ancestor=always, now="x")
    assert st["pending_slugs"] == []
    # a stale run (not a descendant) never clears it, whatever finished
    st2 = ss.update({"scored_sha": "z", "pending_slugs": ["lap"]}, "c", tasks, set(t),
                    ancestor=lambda a, b: False, now="x")
    assert st2["pending_slugs"] == ["lap"] and st2["scored_sha"] == "z"


def test_differently_split_parts_of_another_run_do_not_count_as_covering(tmp_path, monkeypatch):
    """Ids carry the part count: part 1 of 4 is not part 1 of 3."""
    root = _algos(tmp_path, MATRIX)
    t, _ = _plan(root, ["lap"])
    n = len([i for i in t if i.startswith("f-lap-")])
    other = {f"f-lap-p1of{n + 1}"}
    assert not {sp.task_key(x) for x in t.values()} & other


# ------------------------------------------------------------------------------- pipeline --cells

def _matrix_algos():
    mk = lambda s, st, p, c: {"slug": s, "stage": st, "produces": p, "consumes": c}  # noqa: E731
    return ([mk(f, "field-mapping", ["totalfield"], ["phase"]) for f in ("lap", "romeo")]
            + [mk(b, "bfr", ["localfield"], ["totalfield"]) for b in ("lbv", "pdf", "vsharp")]
            + [mk(d, "dipole", ["chimap"], ["localfield"]) for d in ("medi", "rts", "tkd")]
            + [mk("tgv", "bfr+dipole", ["chimap"], ["totalfield"]), mk("e2e", "end-to-end", ["chimap"], ["phase"])])


def _owned(plan):
    cells = {(tfk, b["slug"], d["slug"]) for tfk in plan.fm_keys for b in plan.bfr if plan.owns_col(tfk, b["slug"])
             for d in plan.dipole if plan.composes(d, tfk, b["slug"])}
    spans = {(tfk, s["slug"]) for tfk in plan.fm_keys for s in plan.tf_spans if plan.owns_span(tfk, s["slug"])}
    return cells, spans


def test_cell_ranges_partition_a_job_and_compute_only_what_they_need(pipeline):
    for focus, fieldmaps in (("medi", None), ("lbv", None), ("lap", None), ("tgv", None), ("medi", {"romeo"})):
        whole = pipeline.plan_composed(_matrix_algos(), focus, "sim", None, None, fieldmaps)
        all_cells, all_spans = _owned(whole)
        assert len(all_cells) + len(all_spans) == len(whole.cells) > 0
        for n in (1, 2, 3, 5):
            seen_c, seen_s, e2e = [], [], []
            for k in range(n):
                p = pipeline.plan_composed(_matrix_algos(), focus, "sim", None, None, fieldmaps, (k, n))
                c, s = _owned(p)
                seen_c += sorted(c)
                seen_s += sorted(s)
                e2e += [x["slug"] for x in p.e2e_spans]
                # a part runs only the field maps its cells use
                assert {f["slug"] for f in p.fmap} == {x[0] for x in c | s} - {"gt"}
            assert sorted(seen_c) == sorted(all_cells) and len(seen_c) == len(set(seen_c))
            assert sorted(seen_s) == sorted(all_spans) and len(seen_s) == len(set(seen_s))
            assert e2e == [x["slug"] for x in whole.e2e_spans]       # end-to-end spans: part 0 only
    # a contiguous range stays in few columns: 2 parts of medi's 9 columns need ≤ 2 field maps each
    p = pipeline.plan_composed(_matrix_algos(), "medi", "sim", None, None, None, (0, 3))
    assert [f["slug"] for f in p.fmap] == [] and p.owns_col("gt", "lbv") and not p.owns_col("lap", "lbv")
    with pytest.raises(SystemExit):
        pipeline.parse_cells("3/3")


def test_resume_skips_fresh_cells_after_the_range_split(pipeline):
    whole = pipeline.plan_composed(_matrix_algos(), "medi", "sim", None, None)
    ids = [pipeline.cell_id(c) for c in whole.cells]
    assert ids[0] == "gt~lbv~medi-cmp"
    skip = frozenset(ids[:3])                     # the whole gt column is already scored
    p = pipeline.plan_composed(_matrix_algos(), "medi", "sim", None, None, None, (0, 3), skip)
    assert p.skipped == 3 and not _owned(p)[0] and not p.fmap   # part 0 had exactly those: nothing to do
    p1 = pipeline.plan_composed(_matrix_algos(), "medi", "sim", None, None, None, (1, 3), skip)
    assert p1.skipped == 0 and len(_owned(p1)[0]) == 3            # other parts' ranges do not shift


def _row(id_, sha, combo=None, slug=None, status="ok"):
    return {"id": id_, "mode": "composed", "status": status, "ci_sha": sha, "combo": combo or {},
            "slug": slug or "+".join((combo or {}).values())}


def test_fresh_cell_ids_only_trust_rows_nothing_changed_under(pipeline):
    rows = [_row("a", "s1", {"field_mapping": "gt", "bfr": "lbv", "dipole": "medi"}),
            _row("b", "s1", {"field_mapping": "romeo", "bfr": "lbv", "dipole": "tkd"}),
            _row("c", "s1", {"field_mapping": "gt", "bfr": "pdf", "dipole": "tkd"}, status="DNF"),
            _row("d", "s2", {"field_mapping": "gt", "bfr": "pdf", "dipole": "tkd"}),
            _row("e", "s3", {"field_mapping": "lap"}, slug="tgv"),       # a span row: slug is the span
            _row("f", "s4", {"field_mapping": "gt", "bfr": "pdf", "dipole": "tkd"}),
            {"id": "g", "mode": "isolated", "status": "ok", "ci_sha": "s1", "slug": "medi"}]
    changed = {"s1": {"algorithms/romeo/run.sh", "scripts/score_plan.py"},   # romeo changed since s1
               "s2": {"eval/qsm_eval.py"},                                    # the scorer changed
               "s3": {"algorithms/tgv/algorithm.yml"},
               "s4": None}                                                    # not an ancestor / unknown
    fresh = pipeline.fresh_cell_ids(rows, "HEAD", lambda sha, head: changed[sha])
    assert fresh == {"a"}


def test_fresh_cell_ids_reads_git(pipeline, tmp_path, monkeypatch):
    """The real git path: a row scored at HEAD~1 is fresh unless its method changed in HEAD."""
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    rows = [_row("x", head, {"field_mapping": "gt", "bfr": "lbv-qsmrs", "dipole": "tkd-qsmrs"}),
            _row("y", "0" * 40, {"field_mapping": "gt", "bfr": "lbv-qsmrs", "dipole": "tkd-qsmrs"})]
    assert pipeline.fresh_cell_ids(rows, head) == {"x"}


# ------------------------------------------------------------------------------------------- memory

def test_a_heavy_container_runs_alone_and_is_not_starved(pipeline):
    gate = pipeline.MemoryGate(15.0)
    heavy, light = {"memory_gb": 13}, {}
    log, lock = [], threading.Lock()

    def run(a, name, dur):
        with gate.hold(a):
            with lock:
                log.append(("start", name, gate.used))
            time.sleep(dur)
            with lock:
                log.append(("end", name))
    ts = [threading.Thread(target=run, args=(light, "l1", 0.2))]
    ts[0].start()
    time.sleep(0.05)
    ts += [threading.Thread(target=run, args=(heavy, "h", 0.1))]
    ts[-1].start()
    time.sleep(0.05)
    ts += [threading.Thread(target=run, args=(light, "l2", 0.05))]   # arrives after the heavy one
    ts[-1].start()
    for t in ts:
        t.join()
    order = [e[1] for e in log if e[0] == "start"]
    assert order == ["l1", "h", "l2"]                                 # FIFO: l2 waits behind h
    h_start = log.index(next(e for e in log if e[:2] == ("start", "h")))
    assert ("end", "l1") in log[:h_start]                             # h waited for l1 to finish
    assert next(e for e in log if e[:2] == ("start", "h"))[2] == 13   # and ran alone
    # two light ones share; a heavy one alone always gets in, even over budget
    assert pipeline.memory_need_gb({}) * 2 <= 15
    with pipeline.MemoryGate(5.0).hold({"memory_gb": 40}):
        pass
    assert pipeline.memory_need_gb({"memory_gb": True}) == pipeline.DEFAULT_RUN_GB


def test_methods_with_a_measured_high_peak_declare_it_and_it_never_rescores():
    """BFRnet (QSM.rs) peaks at 12.4 GB (bfrnet-qsmrs-iso resources.json): with a second container on a
    16 GB hosted runner its cells were OOM-killed (exit 137)."""
    spec = sp.load_spec(ROOT / "algorithms", "bfrnet-qsmrs")
    assert spec["memory_gb"] >= 12.4
    assert "memory_gb" in sp.SCORE_COSMETIC
