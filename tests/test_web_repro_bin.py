"""The site's reader for the harmonization binary payloads (web/js/reproBin.js), run under node.

The pages never see the nested per-pipeline structure the payload used to be: they index Float64Array
fit columns by `row * nPairs + pair` and regional runs by structure index. These tests decode a payload
written by the real writers (the `repro_payload` fixture) with the page code and check it against the
Python reader (scripts/repro_format.py), which tests/test_repro_format.py ties to the values the old
all-JSON payload stored — so the site reads exactly those numbers.
"""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

import repro_format as rf

ROOT = Path(__file__).resolve().parent.parent
MODULE = ROOT / "web" / "js" / "reproBin.js"

# Reads index + .bin files from a results dir and prints what the pages would see, NaN as null.
SCRIPT = r"""
const fs = require("fs"), path = require("path");
const B = require(process.argv[1]), dir = process.argv[2], reproName = process.argv[3], regionsName = process.argv[4];
const read = (name) => JSON.parse(fs.readFileSync(path.join(dir, name), "utf8"));
const buffers = (desc) => Object.fromEntries(B.reproBinFiles(desc).map((f) => {
  const b = fs.readFileSync(path.join(dir, f.file));
  return [f.file, b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength)];
}));
const nn = (v) => (v === v ? v : null);
const idx = read(reproName), fits = B.reproFromIndex(idx, B.reproDecodeColumns(idx.fits, buffers(idx.fits)));
const summaryOnly = B.reproFromIndex(idx);
const pipes = {};
for (const [id, node] of Object.entries(fits.pipelines)) {
  const pairs = fits.pairs.map((p, j) => Object.fromEntries(Object.entries(fits.fits).map(([f, col]) => [f, nn(col[node.row * fits.nPairs + j])])));
  pipes[id] = { row: node.row, rejected: node.rejected, n_rejected: node.n_rejected,
                inter_scanner_median_abs_slope_dev: node.inter_scanner_median_abs_slope_dev, pairs };
}
const ri = read(regionsName), reg = B.reproRegionsFromIndex(ri, B.reproDecodeColumns(ri.values, buffers(ri.values)));
const runs = [];
for (const [p, acqs] of Object.entries(reg.runs)) for (const [a, row] of Object.entries(acqs))
  runs.push({ p, a, m: Object.fromEntries(reg.structures.map((s) => [s, nn(row[reg.si[s]])]).filter(([, v]) => v !== null)) });
let refused = false;
try { B.reproDecodeColumns(idx.fits, { ...buffers(idx.fits), [idx.fits.files[0].file]: new ArrayBuffer(8) }); } catch (e) { refused = true; }
console.log(JSON.stringify({ group: fits.group, regionsGroup: reg.group, pipes, nPairs: fits.nPairs, summaryOnlyHasFits: "fits" in summaryOnly,
  summaryOnlyPipes: Object.keys(summaryOnly.pipelines), runs, nRuns: reg.nRuns, refused }));
"""


@pytest.fixture(scope="module", params=list(rf.REPRO_GROUPS))
def decoded(repro_payload, request):
    """One cohort's payloads (results/<stem>.json + <stem>_regions.json) as the page code decodes them."""
    node = shutil.which("node")
    if not node:
        pytest.skip("node not installed")
    out, _ = repro_payload
    names = rf.payload_names(request.param)
    res = subprocess.run([node, "-e", SCRIPT, str(MODULE), str(out), names["repro"], names["regions"]],
                         capture_output=True, text=True, check=True)
    return json.loads(res.stdout), out, names


def test_js_fit_columns_match_the_python_reader(decoded):
    js, out, names = decoded
    py = rf.load_repro(out / names["repro"])
    idx = json.loads((out / names["repro"]).read_text())
    assert js["group"] == idx["group"] == py["group"]
    assert list(js["pipes"]) == list(py["pipelines"]) == idx["pipelines"]
    assert js["nPairs"] == len(idx["pairs"])
    n = 0
    for pid, node in py["pipelines"].items():
        got = js["pipes"][pid]
        assert got["row"] == idx["pipelines"].index(pid)
        assert got["rejected"] == node["rejected"] and got["n_rejected"] == node["n_rejected"]
        assert got["inter_scanner_median_abs_slope_dev"] == node["inter_scanner_median_abs_slope_dev"]
        for p, vals in zip(idx["pairs"], got["pairs"]):
            m = node[p["class"]].get(p["group"], {}).get(p["key"])
            if m is None:
                assert all(v is None for v in vals.values())
                continue
            n += 1
            # every field the JS decoded (incl. the derived |a-1|) is the exact double Python has
            assert vals == {f: m[f] for f in vals}, (pid, p)
            assert set(vals) == set(rf.FIT_DECIMALS) | {"abs_slope_dev"}
    assert n > 50


def test_js_summary_only_load_skips_the_columns(decoded):
    js, out, names = decoded
    assert js["summaryOnlyHasFits"] is False
    assert js["summaryOnlyPipes"] == json.loads((out / names["repro"]).read_text())["pipelines"]


def test_js_regions_match_the_python_reader(decoded):
    js, out, names = decoded
    py = rf.load_regions(out / names["regions"])
    assert js["regionsGroup"] == py["group"]
    key = lambda r: (r["p"], r["a"])
    assert sorted(js["runs"], key=key) == sorted(py["runs"], key=key)
    assert js["nRuns"] == len(py["runs"])


def test_js_refuses_a_buffer_that_does_not_match_its_index(decoded):
    assert decoded[0]["refused"] is True
