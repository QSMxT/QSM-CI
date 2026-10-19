"""Binary columnar storage for the harmonization payloads the site reads.

Two payloads, each a small JSON index plus raw float32 files beside it:

  results/repro.json          index: targets, acquisitions, comparisons, exclusion_rules, `pairs`
                              (the ordered comparison list), `pipelines` (ordered ids), `summary`
                              (per-pipeline headline columns), `rejected`, and `fits` (a descriptor)
  results/repro_fits.bin      per-pair fit stats the web reads     [field][pipeline][pair]
  results/repro_fits_extra.bin  the remaining per-pair fit stats   [field][pipeline][pair]

  results/repro_regions.json  index: targets, acquisitions, structures, `pipelines`, `acqs`, `values`
  results/repro_regions.bin   L/R-merged mean chi (ppb)            [pipeline][acquisition][structure]

A descriptor says how to read its files:

  {"dtype": "<f4", "shape": [...], "decimals": {field: dp},
   "files": [{"file": "repro_fits.bin", "fields": ["slope", ...], "bytes": n, "sha256": "..."}]}

Each file holds one C-order little-endian float32 block of `shape` per field, in `fields` order; NaN
means no value (no fit for that pipeline x pair, no run for that pipeline x acquisition). `file` is
relative to the index. The values are decimals rounded to `decimals` places before they were written,
so a reader rounds back to recover them exactly (float32 carries ~7 significant digits, enough for
every field at the magnitudes these take). `sha256` lets a reader (and the site) detect a stale or
truncated file next to a newer index.

Standard library only, so the dependency-free post-processing scripts can write it too.
"""
from __future__ import annotations

import hashlib
import json
import math
import sys
from array import array
from pathlib import Path

DTYPE = "<f4"
CLASSES = ("test_retest", "inter_scanner", "inter_protocol")
# Per-pair fit stats and the decimals repro_eval.py rounds them to. The site reads the first file
# only, so the stats it never shows stay out of its download. |a-1| is not stored: it is |slope-1|.
FIT_FILES = (("repro_fits.bin", ("slope", "ba_bias_ppm")),
             ("repro_fits_extra.bin", ("intercept_ppm", "pearson_r", "ba_loa_ppm", "n_rois")))
FIT_DECIMALS = {"slope": 4, "ba_bias_ppm": 6, "intercept_ppm": 6, "pearson_r": 4, "ba_loa_ppm": 6,
                "n_rois": 0}
SUMMARY_FIELDS = tuple(f"{c}_{s}" for c in CLASSES
                       for s in ("median_abs_slope_dev", "mean_abs_slope_dev", "n_pairs", "n_possible")) \
    + ("n_possible", "n_rejected", "n_no_recon")


def _size(shape) -> int:
    n = 1
    for d in shape:
        n *= d
    return n


def write_columns(out_dir: Path, files, shape, decimals) -> dict:
    """Write `files` = [(name, {field: flat values})] as float32 blocks; return the descriptor.
    None (or a non-finite value) is stored as NaN."""
    n = _size(shape)
    desc = {"dtype": DTYPE, "shape": list(shape), "decimals": decimals, "files": []}
    for name, cols in files:
        buf = array("f")
        for field, vals in cols.items():
            if len(vals) != n:
                raise ValueError(f"{name}:{field} has {len(vals)} values, shape {shape} needs {n}")
            buf.extend(float("nan") if v is None or not math.isfinite(v) else v for v in vals)
        if sys.byteorder == "big":
            buf.byteswap()
        data = buf.tobytes()
        (Path(out_dir) / name).write_bytes(data)
        desc["files"].append({"file": name, "fields": list(cols), "bytes": len(data),
                              "sha256": hashlib.sha256(data).hexdigest()})
    return desc


def read_columns(index_path: Path, desc: dict, fields=None) -> dict:
    """{field: list of floats (NaN = missing)} for `fields` (default: all), rounded back to their
    decimals. Reads only the files that hold a requested field; checks size and hash."""
    if desc.get("dtype") != DTYPE:
        raise ValueError(f"unsupported dtype {desc.get('dtype')!r}")
    n = _size(desc["shape"])
    dec = desc.get("decimals") or {}
    out = {}
    for f in desc["files"]:
        want = [x for x in f["fields"] if fields is None or x in fields]
        if not want:
            continue
        path = Path(index_path).parent / f["file"]
        data = path.read_bytes()
        if len(data) != f["bytes"] or hashlib.sha256(data).hexdigest() != f["sha256"]:
            raise ValueError(f"{path} does not match {Path(index_path).name} (stale or truncated)")
        buf = array("f")
        buf.frombytes(data)
        if sys.byteorder == "big":
            buf.byteswap()
        for k, field in enumerate(f["fields"]):
            if field not in want:
                continue
            d = dec.get(field) if isinstance(dec, dict) else dec
            block = buf[k * n:(k + 1) * n]
            out[field] = list(block) if d is None else [v if v != v else round(v, d) for v in block]
    return out


def is_binary(doc: dict) -> bool:
    return "fits" in doc or "values" in doc


def load_repro(path) -> dict:
    """repro.json as the nested per-pipeline structure it used to be stored as:
    {targets, acquisitions, comparisons, exclusion_rules, pipelines: {id: {<class>: {group: {pair:
    {slope, intercept_ppm, abs_slope_dev, pearson_r, ba_bias_ppm, ba_loa_ppm, n_rois}}}, <summary>,
    rejected: [...]}}}. A payload still in that form is returned as it is."""
    path = Path(path)
    doc = json.loads(path.read_text())
    if not is_binary(doc):
        return doc
    cols = read_columns(path, doc["fits"])
    pairs, n_pairs = doc["pairs"], len(doc["pairs"])
    pipelines = {}
    for i, pid in enumerate(doc["pipelines"]):
        node = {c: {} for c in CLASSES}
        for j, pr in enumerate(pairs):
            k = i * n_pairs + j
            if cols["slope"][k] != cols["slope"][k]:
                continue
            m = {f: cols[f][k] for f in cols}
            m["abs_slope_dev"] = round(abs(m["slope"] - 1), 4)
            if "n_rois" in m:
                m["n_rois"] = int(m["n_rois"])
            node[pr["class"]].setdefault(pr["group"], {})[pr["key"]] = m
        for f, vals in doc["summary"].items():
            node[f] = vals[i]
        node["rejected"] = [{"class": pairs[r["pair"]]["class"], "group": pairs[r["pair"]]["group"],
                             "pair": pairs[r["pair"]]["key"],
                             **{k: v for k, v in r.items() if k != "pair"}}
                            for r in doc.get("rejected", {}).get(pid, [])]
        pipelines[pid] = node
    return {**{k: doc[k] for k in ("targets", "acquisitions", "comparisons") if k in doc},
            "pipelines": pipelines, "exclusion_rules": doc.get("exclusion_rules")}


def load_regions(path) -> dict:
    """repro_regions.json as its old run list: {targets, acquisitions, structures,
    runs: [{p: pipeline, a: acquisition, m: {structure: chi ppb}}]}. Old-form payloads pass through."""
    path = Path(path)
    doc = json.loads(path.read_text())
    if not is_binary(doc):
        return doc
    vals = read_columns(path, doc["values"])["chi_ppb"]
    structs, acqs = doc["structures"], doc["acqs"]
    ns, na = len(structs), len(acqs)
    runs = []
    for i, p in enumerate(doc["pipelines"]):
        for j, a in enumerate(acqs):
            base = (i * na + j) * ns
            m = {s: vals[base + k] for k, s in enumerate(structs) if vals[base + k] == vals[base + k]}
            if m:
                runs.append({"p": p, "a": a, "m": m})
    return {"targets": doc.get("targets"), "acquisitions": doc.get("acquisitions"),
            "structures": structs, "runs": runs}
