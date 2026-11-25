"""Which acquisition pairs the harmonization fits compare (repro_eval.comparison_plan).

Inter-scanner pairs every run on one scanner with every run on the other: the two sessions are on
different days, so run numbers carry no pairing between them. Test-retest pairs every two runs of
one protocol on one scanner; inter-protocol pairs each protocol with the bridge run of the same
number, acquired in the same session.
"""
from collections import Counter

import repro_eval


def _acqs(sessions, protocols=("bridge", "local"), runs=("run1", "run2", "run3")):
    return {f"{s}-{sc}-{p}-{r}": {"subject": s, "scanner": sc, "protocol": p, "run": r}
            for s, scs in sessions.items() for sc in scs for p in protocols for r in runs}


def test_inter_scanner_pairs_every_run_with_every_run():
    acqs = _acqs({"s1": ["site1-achieva", "site5-mr750", "site5-prisma"]})
    inter = [(a, b) for c, _, _, a, b in repro_eval.comparison_plan(acqs) if c == "inter_scanner"]
    # 3 scanner pairs x 2 protocols x 3 x 3 runs, no pair twice
    assert len(inter) == len(set(inter)) == 3 * 2 * 9
    runs = Counter((acqs[a]["run"], acqs[b]["run"]) for a, b in inter)
    assert len(runs) == 9 and set(runs.values()) == {6}
    assert all(acqs[a]["protocol"] == acqs[b]["protocol"] and acqs[a]["scanner"] != acqs[b]["scanner"]
               for a, b in inter)
    # the reference-site (Site 1) scan stays on x, so slopes read "other scanner vs home"
    assert all(acqs[a]["scanner"] == "site1-achieva" for a, b in inter if "site1-achieva" in (a + b))


def test_test_retest_and_inter_protocol_pairs():
    acqs = _acqs({"s1": ["site1-achieva"]})
    plan = repro_eval.comparison_plan(acqs)
    tr = [(acqs[a], acqs[b]) for c, _, _, a, b in plan if c == "test_retest"]
    assert len(tr) == 2 * 3 and all(x["protocol"] == y["protocol"] and x["run"] != y["run"] for x, y in tr)
    ip = [(acqs[a], acqs[b]) for c, _, _, a, b in plan if c == "inter_protocol"]
    assert len(ip) == 3 and all(x["protocol"] == "bridge" and y["protocol"] == "local" and x["run"] == y["run"]
                                for x, y in ip)


def test_keys_are_unique_within_a_group():
    acqs = _acqs({"s1": ["site1-achieva", "site4-skyra"], "s2": ["site1-achieva", "site6-ingenia"]})
    plan = repro_eval.comparison_plan(acqs)
    keys = [(c, g, k) for c, g, k, _, _ in plan]
    assert len(keys) == len(set(keys))


def test_a_missing_run_drops_only_its_pairs():
    acqs = _acqs({"s1": ["site5-prisma", "site5-mr750"]})
    del acqs["s1-site5-mr750-local-run2"]
    inter = [(a, b) for c, _, _, a, b in repro_eval.comparison_plan(acqs) if c == "inter_scanner"]
    assert len(inter) == 9 + 6 and "s1-site5-mr750-local-run2" not in {x for p in inter for x in p}
