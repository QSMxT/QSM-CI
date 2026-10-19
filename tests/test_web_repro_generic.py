"""Guard: the harmonization (repro) web views are generic over subjects and scanners.

The track started as one subject on two MGH scanners (`prisma`, `cima`) and the site hard-coded
both: scanner lists, `prisma-vs-cima` pairings, acquisition ids parsed by regex. It now carries
several traveling-head subjects on many scanners, and every view reads subject/scanner/protocol/run
from repro.json's `acquisitions` + `comparisons` (or the registry). These tests keep it that way:
no scanner tag may appear as a string literal in the page code outside the display-name map in
js/app.js, and the regional sidecar must carry the metadata the figures pair acquisitions with.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

import repro_format as rf
from repro_format import load_regions

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
REGISTRY = json.loads((ROOT / "scripts" / "datasets.json").read_text())

# a scanner tag (or an acquisition id starting with one) inside a JS string/template literal
LITERAL = re.compile(r"""["'`](?:prisma|cima)(?:["'`]|-(?:bridge|local|pulseq|vs))""")


def _scripts(html: str) -> str:
    return "\n".join(re.findall(r"<script\b[^>]*>(.*?)</script>", html, re.S))


def test_no_hard_coded_scanner_tags_in_page_code():
    sources = {"results.html": _scripts((WEB / "results.html").read_text()),
               "submission.html": _scripts((WEB / "submission.html").read_text()),
               "js/viewer.js": (WEB / "js" / "viewer.js").read_text()}
    hits = [f"{name}: {m.group(0)!r}" for name, src in sources.items() for m in LITERAL.finditer(src)]
    assert not hits, "hard-coded harmonization scanner tags (derive them from data):\n" + "\n".join(hits)


def test_every_registry_scanner_has_a_display_label():
    # Unknown tags still render (label = tag, fallback colour), but a registered scanner should get a
    # proper name; adding a site means adding it to REPRO_SCANNER_META in js/app.js.
    app = (WEB / "js" / "app.js").read_text()
    meta = app[app.index("const REPRO_SCANNER_META"):app.index("};", app.index("const REPRO_SCANNER_META"))]
    known = set(re.findall(r'^\s*"?([a-z0-9-]+)"?\s*:', meta, re.M))
    scanners = {v["scanner"] for v in REGISTRY.values() if v.get("track") == "repro"}
    assert scanners and not scanners - known, f"scanners without a label in app.js: {sorted(scanners - known)}"


def test_regional_sidecar_carries_acquisition_metadata(tmp_path):
    """gen_repro_regions.py writes one regional payload per cohort, each carrying only its own
    acquisitions' metadata and its own subjects' registration targets."""
    repro = {k: v for k, v in REGISTRY.items() if v.get("track") == "repro"}
    by_subject = {}
    for k, v in repro.items():
        by_subject.setdefault(v["subject"], []).append(k)
    picked = [ids[0] for ids in by_subject.values()][:3]       # one acquisition from three subjects
    assert len({rf.group_of(repro[a]) for a in picked}) == 2   # ...spanning both cohorts
    manifest = json.loads((WEB / "algorithms.json").read_text())
    pipe = next(a["slug"] for a in manifest["algorithms"] if a.get("stage") == "end-to-end")
    stats = {"12": {"n": 100, "mean": 0.02}, "13": {"n": 80, "mean": 0.05}}
    src = {"runs": {f"r{i}": {"pipeline": pipe, "acq": a, "rois": {}, "roi_stats": stats}
                    for i, a in enumerate(picked)}}             # no `targets`: derived from the registry
    inp = tmp_path / "rois.json"
    inp.write_text(json.dumps(src))
    subprocess.run([sys.executable, str(ROOT / "scripts" / "gen_repro_regions.py"), str(inp), str(tmp_path)],
                   check=True, capture_output=True)
    for group in rf.REPRO_GROUPS:
        mine = [a for a in picked if rf.group_of(repro[a]) == group]
        doc = load_regions(tmp_path / rf.payload_names(group)["regions"])
        assert "target" not in doc and doc["group"] == group
        assert set(doc["acquisitions"]) == set(mine)
        for a in mine:
            assert doc["acquisitions"][a] == {f: repro[a][f] for f in ("subject", "scanner", "protocol", "run")}
        targets = {v["subject"]: k for k, v in repro.items() if v.get("repro_target") and rf.group_of(v) == group}
        assert doc["targets"] == targets
        assert {r["a"] for r in doc["runs"]} == set(mine)


def test_every_repro_acquisition_names_a_known_cohort():
    """`group` on every repro-track entry, from REPRO_GROUPS; one subject never spans two cohorts; and
    the manifest lists the cohorts the site builds its Harmonization datasets from."""
    repro = {k: v for k, v in REGISTRY.items() if v.get("track") == "repro"}
    assert all(v.get("group") in rf.REPRO_GROUPS for v in repro.values())
    owner = {}
    for v in repro.values():
        assert owner.setdefault(v["subject"], v["group"]) == v["group"], v["subject"]
    assert {v["group"] for v in repro.values() if v["subject"] == "mgh"} == {"harmonization-pilot"}
    assert {v["group"] for v in repro.values() if v["subject"] != "mgh"} == {"harmonization"}
    manifest = json.loads((WEB / "algorithms.json").read_text())
    assert [g["id"] for g in manifest["repro_groups"]] == list(rf.REPRO_GROUPS)
    for g in manifest["repro_groups"]:
        names = rf.payload_names(g["id"])
        assert g["key"] == rf.REPRO_GROUPS[g["id"]]["key"]
        assert g["repro"] == "results/" + names["repro"] and g["regions"] == "results/" + names["regions"]
