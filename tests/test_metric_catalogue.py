"""The scorer's metric set, stages.yml's `scoring` lists and the web catalogue (METRICS in
web/js/app.js) must agree.

A metric the scorer emits but the catalogue lacks renders as a bare key with no tooltip or direction
(or not at all), and one whose `better` is wrong is ranked backwards. Signed metrics (dgm_slope,
dgm_offset_ppm) have no better direction at all: they are catalogued as better: "none" with a
`target`, so the site shows them without ranking them. The catalogue literals run under node.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest
import yaml

from qsm_ci import qsm_eval as qe

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "web" / "js" / "app.js"
SCORING = yaml.safe_load((ROOT / "stages.yml").read_text())["scoring"]

SIGNED = {"dgm_slope": 1, "dgm_offset_ppm": 0, "para_dgm_slope": 1, "para_dgm_offset_ppm": 0}


def _literal(src: str, name: str, close: str) -> str:
    m = re.search(rf"^const {name} = ([\[{{].*?^{re.escape(close)});", src, re.S | re.M)
    assert m, f"{name} not found in {APP}"
    return m.group(1)


@pytest.fixture(scope="module")
def catalogue():
    if not shutil.which("node"):
        pytest.skip("node not available")
    src = APP.read_text()
    js = "console.log(JSON.stringify({METRICS: %s, METRIC_ORDER: %s, CHISEP_ORDER: %s}))" % (
        _literal(src, "METRICS", "}"), _literal(src, "METRIC_ORDER", "]"),
        _literal(src, "CHISEP_ORDER", "]"))
    out = subprocess.run(["node", "-e", js], capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def _seg_truth():
    seg = np.zeros((8, 8, 8), np.uint8)
    for lbl in (1, 2, 3, 4, 5, 6, 7, 8, 11, 16):
        seg.flat[lbl * 20: lbl * 20 + 8] = lbl
    x = np.random.default_rng(0).standard_normal(seg.shape) * 0.05
    return seg, x


def test_chi_scoring_list_is_exactly_what_challenge_metrics_emits():
    seg, x = _seg_truth()
    emitted = qe.challenge_metrics(1.5 * x, x, np.ones(x.shape, np.uint8), seg)
    assert set(emitted) == set(SCORING["chi"])


def test_para_region_metrics_are_listed_for_chisep():
    seg, x = _seg_truth()
    para = qe.chisep_metrics(1.5 * x, x, np.ones(x.shape, np.uint8), seg, component="para")
    for k in ("nrmse_dgm", "dgm_linearity", "dgm_slope", "dgm_offset_ppm", "nrmse_blood", "calc_leak"):
        assert k in para and k in SCORING["chisep"], k


def test_every_scored_chi_metric_is_catalogued(catalogue):
    for k in SCORING["chi"]:
        assert k in catalogue["METRICS"], f"{k} is scored but has no METRICS entry in web/js/app.js"
        assert k in catalogue["METRIC_ORDER"], f"{k} is scored but missing from METRIC_ORDER"


def test_every_catalogued_direction_is_valid(catalogue):
    for k, m in catalogue["METRICS"].items():
        assert m.get("better") in ("lower", "higher", "none"), k
        if m["better"] == "none":
            assert "target" in m, f"{k}: a signed metric needs its ideal `target`"


def test_signed_dgm_metrics_are_informational_not_ranked(catalogue):
    for k, target in SIGNED.items():
        m = catalogue["METRICS"][k]
        assert m["better"] == "none" and m["target"] == target, k
    for k in ("dgm_linearity", "para_dgm_linearity"):
        assert catalogue["METRICS"][k]["better"] == "lower"
    assert {"para_dgm_slope", "para_dgm_offset_ppm"} <= set(catalogue["CHISEP_ORDER"])
