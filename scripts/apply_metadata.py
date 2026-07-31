#!/usr/bin/env python3
"""One-off: annotate every algorithms/<slug>/algorithm.yml with the taxonomy fields
`language`, `family`, `learning`, and fill `engine` where it was missing.

Surgical line insertion (after the top-level `stage:` line) so folded descriptions, comments
and author blocks are preserved. Idempotent: skips a key that is already present. `engine` is
only added when the file has no top-level `engine:` line (existing toolbox strings are kept).
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# slug -> (language, family, learning, engine_if_missing)
#   language: Rust | MATLAB | Python
#   family:   direct | iterative | deep-learning | bayesian
#   learning: none | pretrained | untrained
META = {
    # --- QSMxT / QSM.rs (Rust) -------------------------------------------------------------
    "vsharp":      ("Rust", "iterative", "none", None),
    "sharp":       ("Rust", "iterative", "none", None),
    "resharp":     ("Rust", "iterative", "none", None),
    "pdf":         ("Rust", "iterative", "none", None),
    "lbv":         ("Rust", "iterative", "none", None),
    "ismv":        ("Rust", "iterative", "none", None),
    "harperella":  ("Rust", "iterative", "none", None),
    "iharperella": ("Rust", "iterative", "none", None),
    "rts":         ("Rust", "iterative", "none", None),
    "tv":          ("Rust", "iterative", "none", None),
    "tkd":         ("Rust", "direct",    "none", None),
    "tsvd":        ("Rust", "direct",    "none", None),
    "tikhonov":    ("Rust", "direct",    "none", None),
    "nltv":        ("Rust", "iterative", "none", None),
    "medi":        ("Rust", "iterative", "none", None),
    "ilsqr":       ("Rust", "iterative", "none", None),
    "ndi":         ("Rust", "iterative", "none", None),
    "fansi":       ("Rust", "iterative", "none", None),
    "fansi-tgv":   ("Rust", "iterative", "none", None),
    "l1-qsm":      ("Rust", "iterative", "none", None),
    "wh-qsm":      ("Rust", "iterative", "none", None),
    "hd-qsm":      ("Rust", "iterative", "none", None),
    "tgv":         ("Rust", "iterative", "none", None),
    "qsmart":      ("Rust", "iterative", "none", None),
    # romeo runs via the QSM.rs engine (its `engine:` was blank) -> Rust group.
    "romeo-fieldmap": ("Rust", "direct", "none", "QSMxT / QSM.rs"),
    # --- MATLAB ----------------------------------------------------------------------------
    "amp-pe":                 ("MATLAB", "bayesian",  "none", "AMP-PE (author code)"),
    "matlab-medi":            ("MATLAB", "iterative", "none", "MEDI toolbox"),
    "matlab-tkd":             ("MATLAB", "direct",    "none", "MATLAB reference"),
    "matlab-sti-ilsqr":       ("MATLAB", "iterative", "none", "STI Suite"),
    "matlab-sti-star":        ("MATLAB", "iterative", "none", "STI Suite"),
    "matlab-sti-vsharp":      ("MATLAB", "iterative", "none", "STI Suite"),
    "matlab-sti-iharperella": ("MATLAB", "iterative", "none", "STI Suite"),
    "chi-sep-ilsqr":          ("MATLAB", "iterative", "none", None),  # engine already set
    "chi-sep-medi":           ("MATLAB", "iterative", "none", None),
    "decompose-qsm":          ("MATLAB", "iterative", "none", None),
    # --- Python (deep learning + numerical) ------------------------------------------------
    "qsmnet":       ("Python", "deep-learning", "pretrained", "original author code"),
    "qsmnet-plus":  ("Python", "deep-learning", "pretrained", "original author code"),
    "qsmgan":       ("Python", "deep-learning", "pretrained", "original author code"),
    "xqsm":         ("Python", "deep-learning", "pretrained", "original author code"),
    "lpcnn":        ("Python", "deep-learning", "pretrained", "original author code"),
    "modl-qsm":     ("Python", "deep-learning", "pretrained", "original author code"),
    "ir2qsm":       ("Python", "deep-learning", "pretrained", "original author code"),
    "autoqsm":      ("Python", "deep-learning", "pretrained", "original author code"),
    "nextqsm":      ("Python", "deep-learning", "pretrained", "original author code"),
    "iqsm-plus":    ("Python", "deep-learning", "pretrained", "original author code"),
    "iqsm":         ("Python", "deep-learning", "pretrained", None),  # engine 'iQSM (PyTorch)'
    "bfrnet":       ("Python", "deep-learning", "pretrained", None),  # engine 'ONNX Runtime'
    "chi-sepnet":   ("Python", "deep-learning", "pretrained", None),  # engine chi-sep χ-sepnet
    "susep-net":    ("Python", "deep-learning", "pretrained", None),  # engine SUSEP-Net
    "inr-qsm":      ("Python", "deep-learning", "untrained",  "original author code"),
    "modip":        ("Python", "deep-learning", "untrained",  "original author code"),
    "wavesep":      ("Python", "iterative",     "none",       None),  # engine WaveSep
    "laplacian-fieldmap": ("Python", "direct",  "none",       "QSM-CI reference"),
}


def patch(slug: str, language: str, family: str, learning: str, engine: str | None) -> str:
    p = ROOT / "algorithms" / slug / "algorithm.yml"
    text = p.read_text()
    lines = text.splitlines(keepends=True)

    has = lambda key: any(re.match(rf"^{key}\s*:", ln) for ln in lines)
    add = []
    if not has("language"):
        add.append(f"language: {language}\n")
    if not has("family"):
        add.append(f"family: {family}\n")
    if not has("learning"):
        add.append(f"learning: {learning}\n")
    if engine and not has("engine"):
        add.append(f"engine: {engine}\n")
    if not add:
        return "skip"

    # insert after the top-level `stage:` line (present in every manifest)
    for i, ln in enumerate(lines):
        if re.match(r"^stage\s*:", ln):
            if not ln.endswith("\n"):
                lines[i] = ln + "\n"
            lines[i + 1:i + 1] = add
            p.write_text("".join(lines))
            return "patched"
    raise SystemExit(f"{slug}: no top-level `stage:` line to anchor on")


def main() -> None:
    dirs = {d.name for d in (ROOT / "algorithms").glob("*/") if not d.name.startswith("_")}
    missing_meta = dirs - META.keys()
    missing_dir = META.keys() - dirs
    if missing_meta:
        raise SystemExit(f"algorithms with no metadata entry: {sorted(missing_meta)}")
    if missing_dir:
        raise SystemExit(f"metadata for non-existent algorithms: {sorted(missing_dir)}")
    n = {"patched": 0, "skip": 0}
    for slug in sorted(META):
        n[patch(slug, *META[slug])] += 1
    print(f"patched {n['patched']}, skipped {n['skip']} (already had fields)")


if __name__ == "__main__":
    main()
