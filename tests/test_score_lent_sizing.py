"""score_plan sizing on the lent runners (highmem / highmem-long): parts of at most LENT_MAX_HOURS, a
job cap below the runner's 13-h shutdown, re-dispatches that skip what is already scored, and
pending_manual bookkeeping when parts finish in separate runs.

The lent runner is shut down 13 h after a job starts, and that shutdown skips the always() upload:
f-inr-qsm-gt (score runs 43137514862, 44654877699, 45292298269) and f-inr-qsm-romeo-qsmrs
(45292298269) each lost every row they had finished. INR-QSM runs ~5-7 h per inversion, so its
unsplit gt job (isolated default + tuned + 2 gt cells, ~4 inversions) can never finish.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


sp, ss, sf = _load("score_plan"), _load("score_state"), _load("score_fresh")

REG = {"sim": {"track": "sim", "active": True, "default": True},
       "invivo": {"track": "invivo", "active": True, "default": True}}
LENT = "neurodesk-arcrunner-lent-qsmci"
ALGOS = {
    "romeo": "stage: field-mapping\nimage: x\n",
    "lap": "stage: field-mapping\nimage: x\n",
    "vsharp": "stage: bfr\nimage: x\n",
    "pdf": "stage: bfr\nimage: x\n",
    "tkd": "stage: dipole\nimage: x\n",
    # INR-QSM-like: highmem-long, tuned on sim and in vivo, composed with 2 bfrs on gt + 2 field maps
    "inr": ("stage: dipole\nimage: x\nrunner: highmem-long\ntimeout_minutes: 7200\njobs: 1\n"
            "compose:\n  fieldmaps: [gt, romeo, lap]\n  bfrs: [vsharp, pdf]\n"
            "parameters:\n- name: tv\n  default: 0.15\n  tuned:\n    sim: 0.01\n    invivo: 0.02\n"),
    # MoDIP-like: no tuning, quicker per cell
    "mod": ("stage: dipole\nimage: x\nrunner: highmem-long\ntimeout_minutes: 7200\njobs: 1\n"
            "compose:\n  fieldmaps: [gt, romeo, lap]\n  bfrs: [vsharp, pdf]\n"),
}


def _iso(slug, rt, variant="default", track="sim", status="ok"):
    return {"id": f"{slug}-iso", "track": track, "mode": "isolated", "slug": slug, "variant": variant,
            "runtime_s": rt, "status": status}


def _cmp(fm, bfr, dip, rt, sha=None):
    r = {"id": f"{fm}~{bfr}~{dip}-cmp", "track": "sim", "mode": "composed", "status": "ok", "runtime_s": rt,
         "combo": {"field_mapping": fm, "bfr": bfr, "dipole": dip}, "slug": f"{bfr}+{dip}"}
    if sha:
        r["ci_sha"] = sha
    return r


# What results/index.json records today: INR-QSM's isolated sim rows are DNFs (no runtime), its
# composed rows ~5.2 h each; MoDIP 2.9 h isolated but 1.3 h per cell.
RUNS = ([_iso(s, rt) for s, rt in {"romeo": 15, "lap": 19, "vsharp": 10, "pdf": 27, "tkd": 60, "mod": 10263}.items()]
        + [{"id": "inr-iso", "track": "sim", "mode": "isolated", "slug": "inr", "status": "DNF"}]
        + [_cmp(fm, b, "inr", 18700) for fm in ("romeo", "lap") for b in ("vsharp", "pdf")]
        + [_cmp(fm, b, "mod", 4700) for fm in ("gt", "romeo", "lap") for b in ("vsharp", "pdf")]
        + [_iso("inr", 12128, track="invivo"), _iso("inr", 11785, "tuned", track="invivo"),
           _iso("mod", 4157, track="invivo")])


@pytest.fixture
def root(tmp_path, monkeypatch):
    monkeypatch.setenv("QSMCI_HIGHMEM_RUNNER", LENT)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    r = tmp_path / "algorithms"
    for slug, body in ALGOS.items():
        (r / slug).mkdir(parents=True)
        (r / slug / "algorithm.yml").write_text(body)
    return r


def _decide(root, scope, state=None, fresh=frozenset(), runs=RUNS):
    return sp.decide({"EVENT": "workflow_dispatch", "SHA": "HEAD", "SCOPE": scope}, root, REG, state or {},
                     runs=runs, fresh=set(fresh))


# ------------------------------------------------------------------------------------------- sizing

def test_costs_come_from_composed_rows_when_the_isolated_run_never_finished():
    c = sp.stage_costs(RUNS)
    assert c["inr"]["composed"] == pytest.approx(18700 - 15 - 10, abs=20)
    assert sp._cost(c, "inr") == c["inr"]["composed"] and sp._cost(c, "inr", "tuned") == c["inr"]["composed"]
    assert sp._cost(c, "mod") == 10263 and sp._cost(c, "mod", composed=True) < 4700   # a cell: 1.3 h
    assert c["inr"]["invivo-tuned"] == 11785


def test_a_highmem_long_dipole_is_split_into_parts_of_at_most_8_hours(root):
    d = _decide(root, "inr")
    ids = [t["id"] for t in d["tasks"]]
    # one inversion per job: each isolated variant alone, each field map's 2 cells in 2 parts
    assert ids == ["f-inr-iso-default", "f-inr-iso-tuned", "f-inr-gt-p1of2", "f-inr-gt-p2of2",
                   "f-inr-romeo-p1of2", "f-inr-romeo-p2of2", "f-inr-lap-p1of2", "f-inr-lap-p2of2", "iv-inr"]
    t = {x["id"]: x for x in d["tasks"]}
    assert [t[i].get("variants") for i in ids[:2]] == ["default", "tuned"]
    assert all(t[i]["mode"] == "isolated" and "fieldmaps" not in t[i] for i in ids[:2])
    assert all(t[i]["mode"] == "composed" and t[i]["cells"] in ("0/2", "1/2") for i in ids[2:8])
    assert all(h <= sp.LENT_MAX_HOURS for h in d["estimates"].values()) and max(d["estimates"].values()) > 4
    for x in d["tasks"]:
        assert x["runs_on"] == LENT and x["timeout"] == sp.LENT_JOB_MINUTES < 13 * 60 and x["resume"] == "true"
    assert d["max_parallel"] == 1                                   # parts queue on the one runner
    assert t["f-inr-gt-p1of2"]["replaces"] == "f-inr,f-inr-gt" and t["f-inr-iso-tuned"]["replaces"] == "f-inr,f-inr-gt"
    assert any("lent-runner job(s) sized to 8 h" in n for n in d["notes"])
    # the matrix job name still starts with the id (score_plan.in_progress_runs, the reaper)
    assert all(list(x)[0] == "id" for x in d["tasks"])


def test_a_part_that_fits_keeps_its_isolated_runs_and_cells_together(root):
    d = _decide(root, "mod")
    assert [t["id"] for t in d["tasks"]] == ["f-mod-gt", "f-mod-romeo", "f-mod-lap", "iv-mod"]
    assert d["estimates"]["f-mod-gt"] == pytest.approx((10263 + 2 * (4700 - 25) + 37) / 3600, rel=0.05)
    assert d["tasks"][0]["mode"] == "both"


def test_the_target_part_length_is_configurable(root, monkeypatch):
    monkeypatch.setattr(sp, "LENT_MAX_HOURS", 12.0)
    ids = [t["id"] for t in _decide(root, "inr")["tasks"]]
    # two inversions now fit a part: isolated default + tuned together, a field map's 2 cells together
    assert ids == ["f-inr-iso", "f-inr-gt-p1of1", "f-inr-romeo", "f-inr-lap", "iv-inr"]


def test_an_in_vivo_job_too_long_for_one_part_is_split_by_variant(root):
    runs = [r for r in RUNS if r.get("track") != "invivo"] + [_iso("inr", 20000, track="invivo"),
                                                               _iso("inr", 20000, "tuned", track="invivo")]
    t = {x["id"]: x for x in _decide(root, "inr", runs=runs)["tasks"]}
    assert t["iv-inr-default"]["variants"] == "default" and t["iv-inr-tuned"]["variants"] == "tuned"
    assert "iv-inr" not in t and t["iv-inr-tuned"]["replaces"] == "iv-inr"


def test_hosted_sizing_is_unchanged_by_the_lent_rules(root):
    """The 3-h hosted target and its matrix-size steps still apply to hosted methods only."""
    d = _decide(root, "tkd")
    assert [t["id"] for t in d["tasks"]] == ["f-tkd", "iv-tkd"] and d["max_parallel"] is None
    assert "resume" not in d["tasks"][0]                       # an explicit hosted dispatch rescores


# ------------------------------------------------------------------------------ resume / re-dispatch

def test_a_re_dispatch_plans_only_the_parts_still_owed(root):
    """A part cut off (or capped at LENT_JOB_MINUTES) publishes the rows it finished; the next
    scope=inr dispatch settles every part whose rows are all fresh and runs only the rest."""
    fresh = {"inr-iso", "inr-iso-tuned", "gt~pdf~inr-cmp", "gt~vsharp~inr-cmp", "lap~pdf~inr-cmp",
             "inr-iso-invivo", "inr-iso-tuned-invivo"}
    d = _decide(root, "inr", fresh=fresh)
    # cells of a field map in bfr order: (pdf), (vsharp); field maps in `compose:` order
    assert [t["id"] for t in d["tasks"]] == ["f-inr-romeo-p1of2", "f-inr-romeo-p2of2", "f-inr-lap-p2of2"]
    assert [t["id"] for t in d["settled"]] == ["f-inr-iso-default", "f-inr-iso-tuned", "f-inr-gt-p1of2",
                                               "f-inr-gt-p2of2", "f-inr-lap-p1of2", "iv-inr"]
    assert all(t["settled"] == "fresh" for t in d["settled"])
    # a part with one fresh cell still runs, and its job skips that cell (pipeline.py --resume)
    d = _decide(root, "inr", fresh={"lap~pdf~inr-cmp"})
    assert "f-inr-lap-p1of2" not in {t["id"] for t in d["tasks"]}
    assert "f-inr-lap-p2of2" in {t["id"] for t in d["tasks"]}


def test_pending_manual_clears_when_the_parts_finish_in_separate_runs(root):
    """The current state owes the old by-field-map ids (f-inr, f-inr-gt, …). Run 1 finishes some
    parts and is cut off in others; run 2 (a re-dispatch) settles the finished ones, runs the rest,
    and the old entries clear only then."""
    always = lambda a, b: True  # noqa: E731
    state = {"scored_sha": "a", "pending_manual": ["f-inr", "f-inr-gt", "f-inr-lap", "f-inr-romeo", "iv-inr"]}
    run1 = _decide(root, "inr", state)
    tasks1 = run1["tasks"] + run1["settled"]
    cut = {"f-inr-gt-p2of2", "f-inr-romeo-p2of2"}
    st = ss.update(state, "b", tasks1, {t["id"] for t in tasks1} - cut, ancestor=always, now="x")
    assert st["pending_manual"] == ["f-inr", "f-inr-gt", "f-inr-romeo"]   # lap and iv paid off
    assert st["pending_slugs"] == ["inr"]
    # run 2: every part run 1 finished published fresh rows
    fresh = {"inr-iso", "inr-iso-tuned", "gt~pdf~inr-cmp", "lap~pdf~inr-cmp", "lap~vsharp~inr-cmp",
             "romeo~pdf~inr-cmp", "inr-iso-invivo", "inr-iso-tuned-invivo"}
    run2 = _decide(root, "inr", st, fresh)
    assert [t["id"] for t in run2["tasks"]] == sorted(cut)
    tasks2 = run2["tasks"] + run2["settled"]
    assert ss.done_ids(tasks2, Path("/nonexistent")) == {t["id"] for t in run2["settled"]}
    st2 = ss.update(st, "c", tasks2, {t["id"] for t in tasks2}, ancestor=always, now="x")
    assert st2["pending_manual"] == [] and st2["pending_slugs"] == []


def test_a_push_owes_only_the_parts_that_are_not_fresh(root):
    """A push run never schedules lent work; it records what it owes as pending_manual part ids."""
    fresh = {"inr-iso", "inr-iso-tuned", "inr-iso-invivo", "inr-iso-tuned-invivo"}
    d = sp.decide({"EVENT": "push", "SHA": "HEAD"}, root, REG,
                  {"scored_sha": "HEAD", "pending_slugs": ["inr"]}, runs=RUNS, fresh=fresh)
    assert not d["tasks"]
    assert "f-inr-gt-p1of2" in d["skipped_manual"] and "f-inr-iso-default" not in d["skipped_manual"]


def test_plan_output_hands_merge_the_settled_parts_but_never_schedules_them(root, tmp_path, monkeypatch):
    out = tmp_path / "out"
    for k, v in {"EVENT": "workflow_dispatch", "SHA": "HEAD", "SCOPE": "mod", "GITHUB_OUTPUT": str(out),
                 "QSMCI_ALGORITHMS_DIR": str(root)}.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setattr(sp, "load_runs", lambda *a: RUNS)
    monkeypatch.setattr(sp.score_fresh, "fresh_ids", lambda *a, **k: frozenset({"mod-iso-invivo"}))
    sp.main()
    o = {k: json.loads(v) for k, v in (line.split("=", 1) for line in out.read_text().splitlines())
         if k in ("tasks", "hosted_tasks")}
    assert "iv-mod" in {t["id"] for t in o["tasks"]} and "iv-mod" not in {t["id"] for t in o["hosted_tasks"]}


# ----------------------------------------------------------------------------------- freshness rules

def test_isolated_ids_match_the_scorer(root):
    import sys
    sys.path.insert(0, str(ROOT / "scripts"))
    import pipeline
    from types import SimpleNamespace
    for track in ("sim", "invivo"):
        args = SimpleNamespace(track=track, phantom_sfx="", inputs_sfx="")
        assert sp.iso_unit_ids("inr", ["default", "tuned"], track) == \
            [pipeline.iso_run_id("inr", v, args) for v in ("default", "tuned")]
    rows = [{"id": "inr-iso", "mode": "isolated", "status": "ok", "ci_sha": "s1", "slug": "inr"},
            {"id": "x-cmp", "mode": "composed", "status": "ok", "ci_sha": "s1", "slug": "pdf+inr",
             "combo": {"field_mapping": "gt", "bfr": "pdf", "dipole": "inr"}}]
    same = lambda a, b: set()  # noqa: E731
    assert pipeline.fresh_cell_ids(rows, "HEAD", same) == {"x-cmp"}
    assert pipeline.fresh_cell_ids(rows, "HEAD", same, modes=("isolated",)) == {"inr-iso"}


def test_skip_score_commits_do_not_make_rows_stale(tmp_path):
    """A `[skip score]` commit is left out of a run's scope; it does not invalidate a row either, so a
    scheduling-only change (this one included) does not throw away hours of lent-runner rows."""
    g = lambda *a: subprocess.run(["git", *a], cwd=tmp_path, check=True, capture_output=True,  # noqa: E731
                                  text=True).stdout.strip()
    g("init", "-q", "-b", "main")
    g("config", "user.email", "t@t")
    g("config", "user.name", "t")
    (tmp_path / "a").write_text("1")
    g("add", "-A")
    g("commit", "-qm", "base")
    base = g("rev-parse", "HEAD")
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "pipeline.py").write_text("x")
    g("add", "-A")
    g("commit", "-qm", "scheduling only [skip score]\n\nbody")
    assert sf.git_changed(base, "HEAD", tmp_path) == set()
    (tmp_path / "algorithms" / "inr").mkdir(parents=True)
    (tmp_path / "algorithms" / "inr" / "run.sh").write_text("y")
    g("add", "-A")
    g("commit", "-qm", "inr: change")
    assert sf.git_changed(base, "HEAD", tmp_path) == {"algorithms/inr/run.sh"}
    assert sf.git_changed("HEAD", base, tmp_path) is None           # not an ancestor: unknown
