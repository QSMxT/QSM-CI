"""Binary columnar storage for the harmonization payloads the site reads.

The harmonization acquisitions fall into independent COHORTS, named by each repro-track registry
entry's `group` (scripts/datasets.json) and described in REPRO_GROUPS below: the EMTP traveling heads
(`harmonization`) and the MGH pilot (`harmonization-pilot`). Each cohort is its own dataset on the
site, so each gets its own payload set, named from the cohort's file stem (`repro` for the traveling
heads, `repro_pilot` for the pilot). Nothing in one cohort's files counts or ranks anything of
another's. Per cohort, two payloads, each a small JSON index plus raw float32 files beside it:

  results/<stem>.json            index: group, targets, acquisitions, comparisons, exclusion_rules,
                                 `pairs` (the ordered comparison list), `pipelines` (ordered ids),
                                 `summary` (per-pipeline headline columns), `rejected`, and `fits`
                                 (a descriptor)
  results/<stem>_fits.bin        per-pair fit stats the web reads     [field][pipeline][pair]
  results/<stem>_fits_extra.bin  the remaining per-pair fit stats     [field][pipeline][pair]

  results/<stem>_regions.json    index: group, targets, acquisitions, structures, `pipelines`, `acqs`,
                                 `values`
  results/<stem>_regions.bin     L/R-merged mean chi (ppb)            [pipeline][acquisition][structure]

A descriptor says how to read its files:

  {"dtype": "<f4", "shape": [...], "decimals": {field: dp},
   "files": [{"file": "<stem>_fits.bin", "fields": ["slope", ...], "bytes": n, "sha256": "..."}]}

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

# The harmonization cohorts, in the order the site shows them (the first is the default). A
# repro-track registry entry names its cohort in `group`; one without it belongs to DEFAULT_GROUP.
#   key    the site's dataset key (results.html?dataset=<key>)
#   label  the dataset tab's name
#   stem   the payload file stem under results/ (see the module docstring)
# A new cohort is a new entry here plus its acquisitions' `group`; the writers, the manifest
# (gen_manifest.py copies this into web/algorithms.json as `repro_groups`) and the site pick it up.
REPRO_GROUPS = {
    "harmonization": {"key": "repro", "label": "Harmonization (2026)", "stem": "repro",
                      "description": "EMTP traveling heads"},
    "harmonization-pilot": {"key": "repro-pilot", "label": "Harmonization pilot (MGH)",
                            "stem": "repro_pilot", "description": "MGH pilot"},
}
DEFAULT_GROUP = "harmonization"


def group_of(entry: dict) -> str:
    """The cohort a repro-track registry entry belongs to."""
    return entry.get("group") or DEFAULT_GROUP


def fit_files(stem: str) -> tuple:
    """(file name, fields) per fit-column file of the cohort with this stem."""
    return tuple((f"{stem}{suffix}", fields) for suffix, fields in FIT_FILE_FIELDS)


def payload_names(group: str) -> dict:
    """The file names (relative to results/) of one cohort's payloads."""
    stem = REPRO_GROUPS[group]["stem"]
    return {"repro": f"{stem}.json", "fits": [n for n, _ in fit_files(stem)],
            "regions": f"{stem}_regions.json", "regions_bin": f"{stem}_regions.bin"}


def all_payload_names() -> list:
    """Every committed harmonization payload file, every cohort (what the workflows commit)."""
    out = []
    for g in REPRO_GROUPS:
        n = payload_names(g)
        out += [n["repro"], *n["fits"], n["regions"], n["regions_bin"]]
    return out


# Per-pair fit stats and the decimals repro_eval.py rounds them to. The site reads the first file
# only, so the stats it never shows stay out of its download. |a-1| is not stored: it is |slope-1|.
FIT_FILE_FIELDS = (("_fits.bin", ("slope", "ba_bias_ppm")),
                   ("_fits_extra.bin", ("intercept_ppm", "pearson_r", "ba_loa_ppm", "n_rois")))
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
    """A cohort's repro payload (results/<stem>.json) as the nested per-pipeline structure it used to
    be stored as: {group, targets, acquisitions, comparisons, exclusion_rules, pipelines: {id:
    {<class>: {<comparison group>: {pair: {slope, intercept_ppm, abs_slope_dev, pearson_r,
    ba_bias_ppm, ba_loa_ppm, n_rois}}}, <summary>, rejected: [...]}}}. A payload still in that form is returned as it is."""
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
    return {**{k: doc[k] for k in ("group", "targets", "acquisitions", "comparisons") if k in doc},
            "pipelines": pipelines, "exclusion_rules": doc.get("exclusion_rules")}


def load_regions(path) -> dict:
    """A cohort's regions payload (results/<stem>_regions.json) as its old run list: {group, targets,
    acquisitions, structures, runs: [{p: pipeline, a: acquisition, m: {structure: chi ppb}}]}.
    Old-form payloads pass through."""
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
    return {"group": doc.get("group"), "targets": doc.get("targets"),
            "acquisitions": doc.get("acquisitions"), "structures": structs, "runs": runs}
