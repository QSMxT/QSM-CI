"""The results page's equivalent `qsmxt run` command (web/js/qsmxtCommand.js).

The command must use QSMxT's CLI values, never QSM-CI slugs (`--bf-algorithm vsharp`, not
`vsharp-qsmrs`), and must be absent when a pipeline has no faithful `qsmxt run` equivalent. The JS
module is pure, so it runs here under node against the generated web/algorithms.json.

The value sets below are copied from QSMxT's `src/cli.rs` (UnwrapAlgorithmArg, BfAlgorithmArg,
QsmAlgorithmArg; clap's kebab-case names). Update them when QSMxT's CLI changes.
"""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
MODULE = ROOT / "web" / "js" / "qsmxtCommand.js"
MANIFEST = ROOT / "web" / "algorithms.json"

QSMXT_VALUES = {
    "--unwrapping-algorithm": {"romeo", "laplacian"},
    "--bf-algorithm": {"vsharp", "pdf", "lbv", "ismv", "sharp", "resharp", "harperella",
                       "iharperella", "bfrnet", "iqfm"},
    "--qsm-algorithm": {"rts", "tv", "tkd", "tsvd", "tgv", "tikhonov", "nltv", "medi", "tfi",
                        "ilsqr", "lsqr", "heidi", "qsmart", "ndi", "fansi", "fansi-tgv", "l1qsm",
                        "whqsm", "hdqsm", "amp-pe", "xqsm", "qsmnet", "qsmnet-plus", "autoqsm",
                        "qsmgan", "ir2qsm", "lpcnn", "modl-qsm", "nextqsm", "iqsm", "iqsm-plus"},
}
# Flags (beyond the algorithm flags) that the command may carry; all exist on `qsmxt run`.
EXTRA_FLAGS = {"--no-medi-smv"}

# laplacian-qsmrs as PR #284 adds it, so the field-mapping value is covered before it lands.
LAPLACIAN_FIXTURE = {"slug": "laplacian-qsmrs", "stage": "field-mapping", "algorithm": "laplacian",
                     "engine": "QSMxT / QSM.rs"}

PIPELINES = {
    "romeo+vsharp+rts": ["romeo-qsmrs", "vsharp-qsmrs", "rts-qsmrs"],
    "laplacian+pdf+tv": ["laplacian-qsmrs", "pdf-qsmrs", "tv-qsmrs"],
    "harperella+rts": ["harperella-qsmrs", "rts-qsmrs"],
    "harperella": ["harperella-qsmrs"],
    "romeo+tgv": ["romeo-qsmrs", "tgv-qsmrs"],
    "tgv": ["tgv-qsmrs"],
    "romeo+qsmart": ["romeo-qsmrs", "qsmart-qsmrs"],
    "romeo+vsharp+medi": ["romeo-qsmrs", "vsharp-qsmrs", "medi-qsmrs"],
    "romeo+vsharp+fansi-nltgv": ["romeo-qsmrs", "vsharp-qsmrs", "fansi-nltgv-qsmrs"],
    "romeo+bfrnet+rts": ["romeo-qsmrs", "bfrnet", "rts-qsmrs"],    # BFRnet is not QSM.rs
    "romeo+vsharp+ilsqr-sti": ["romeo-qsmrs", "vsharp-qsmrs", "ilsqr-sti"],
    "decompose": ["decompose-qsmrs"],                               # chi-separation stage
}

HEAD = "qsmxt run /path/to/bids /path/to/output"


@pytest.fixture(scope="module")
def commands():
    node = shutil.which("node")
    if not node:
        pytest.skip("node not installed")
    algos = json.loads(MANIFEST.read_text())["algorithms"]
    by_slug = {a["slug"]: a for a in algos}
    by_slug.setdefault(LAPLACIAN_FIXTURE["slug"], LAPLACIAN_FIXTURE)
    singles = {a["slug"]: [a["slug"]] for a in by_slug.values()}
    script = (
        f"import {{ qsmxtCommand }} from {json.dumps(MODULE.as_uri())};\n"
        "const { bySlug, cases } = JSON.parse(process.argv[1]);\n"
        "const out = {};\n"
        "for (const [k, steps] of Object.entries(cases)) out[k] = qsmxtCommand(steps, bySlug);\n"
        "console.log(JSON.stringify(out));\n"
    )
    payload = json.dumps({"bySlug": by_slug, "cases": {**{f"single:{k}": v for k, v in singles.items()},
                                                      **PIPELINES}})
    res = subprocess.run([node, "--input-type=module", "-e", script, payload],
                         capture_output=True, text=True, check=True)
    return json.loads(res.stdout), by_slug


def _args(cmd):
    """The flag lines of a command, as {flag: value} plus the extra flags."""
    lines = [ln.strip().rstrip("\\").strip() for ln in cmd.split("\n")]
    assert lines[0] == HEAD
    pairs, extra = [], []
    for ln in lines[1:]:
        flag, value, *rest = ln.split()
        pairs.append((flag, value))
        extra += rest
    return pairs, extra


def test_pipeline_commands(commands):
    out, _ = commands
    assert out["romeo+vsharp+rts"] == (f"{HEAD} \\\n  --unwrapping-algorithm romeo \\\n"
                                        "  --bf-algorithm vsharp \\\n  --qsm-algorithm rts")
    assert out["laplacian+pdf+tv"] == (f"{HEAD} \\\n  --unwrapping-algorithm laplacian \\\n"
                                        "  --bf-algorithm pdf \\\n  --qsm-algorithm tv")
    assert out["romeo+tgv"] == f"{HEAD} \\\n  --unwrapping-algorithm romeo \\\n  --qsm-algorithm tgv"
    assert out["tgv"] == f"{HEAD} \\\n  --qsm-algorithm tgv"
    assert out["romeo+qsmart"] == f"{HEAD} \\\n  --unwrapping-algorithm romeo \\\n  --qsm-algorithm qsmart"
    assert out["romeo+vsharp+medi"].endswith("--qsm-algorithm medi --no-medi-smv")
    assert out["romeo+vsharp+fansi-nltgv"].endswith("--qsm-algorithm fansi-tgv")


def test_no_command_without_a_faithful_equivalent(commands):
    out, _ = commands
    # qsmxt run unwraps and fits the field before HARPERELLA; QSM-CI runs it on wrapped phase.
    assert out["harperella"] is None
    assert out["harperella+rts"] is None
    assert out["single:iharperella-qsmrs"] is None
    # A non-QSM.rs step anywhere in the pipeline.
    assert out["romeo+bfrnet+rts"] is None
    assert out["romeo+vsharp+ilsqr-sti"] is None
    # Not a qsmxt run reconstruction stage.
    assert out["decompose"] is None


def test_every_command_uses_qsmxt_cli_values(commands):
    """Every QSM.rs method that gets a command names a value `qsmxt run` accepts — no slugs."""
    out, by_slug = commands
    produced = 0
    for key, cmd in out.items():
        if cmd is None:
            continue
        pairs, extra = _args(cmd)
        for flag, value in pairs:
            assert value in QSMXT_VALUES.get(flag, set()), f"{key}: {flag} {value} is not a QSMxT value"
        assert set(extra) <= EXTRA_FLAGS, f"{key}: unexpected flags {extra}"
        produced += 1
    # Every QSM.rs reconstruction method except the unwrap+bfr spans gets a single-method command.
    expect = {s for s, a in by_slug.items() if "QSM.rs" in (a.get("engine") or "")
              and a["stage"] in ("field-mapping", "bfr", "dipole", "bfr+dipole", "end-to-end")}
    got = {k.split(":", 1)[1] for k, v in out.items() if k.startswith("single:") and v}
    assert got == expect
    assert produced > len(PIPELINES)


def test_manifest_carries_algorithm():
    algos = json.loads(MANIFEST.read_text())["algorithms"]
    assert all(a.get("algorithm") for a in algos)
