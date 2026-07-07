#!/usr/bin/env python3
"""Generate QSM-CI submissions that wrap QSMxT (the QSM.rs Rust engine).

Each algorithm becomes a folder under algorithms/<slug>/ with algorithm.yml, run.sh,
and README.md. All share one environment image (the qsmxt binary); run.sh calls the matching
`qsmxt bgremove <algo>` / `qsmxt invert <algo>` subcommand. Re-run to regenerate.

Citations/DOIs are best-effort primary references — verify before publishing.
"""
from __future__ import annotations

import os
import stat
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IMAGE = "ghcr.io/astewartau/qsm-ci/qsmxt:v1"
QSM_RS = "https://github.com/astewartau/QSM.rs"
QSMXT = "https://github.com/QSMxT/QSMxT"

# stage -> (input artifact, output artifact, qsmxt subcommand group)
STAGE = {
    "bfr":    ("totalfield", "localfield", "bgremove"),
    "dipole": ("localfield", "chimap",     "invert"),
}

# slug, stage, qsmxt algo name, display name, description, citation, doi, [(param, default, desc)]
ALGOS = [
    # --- background field removal ---
    ("vsharp", "bfr", "vsharp", "V-SHARP",
     "Variable-radius SHARP: SMV deconvolution with a spatially varying kernel radius.",
     "Wu et al., Magn Reson Med 2012", None,
     [("threshold", "0.02", "deconvolution threshold"),
      ("max_radius_factor", "0.5", "× min voxel size"),
      ("min_radius_factor", "0.0", "× max voxel size")]),
    ("sharp", "bfr", "sharp", "SHARP",
     "Sophisticated Harmonic Artifact Reduction for Phase data: SMV deconvolution.",
     "Schweser et al., NeuroImage 2011", "10.1016/j.neuroimage.2010.10.070",
     [("threshold", "0.02", "deconvolution threshold"), ("radius_factor", "0.5", "× min voxel size")]),
    ("resharp", "bfr", "resharp", "RESHARP",
     "Regularized SHARP with Tikhonov regularization of the deconvolution.",
     "Sun & Wilman, Magn Reson Med 2014", "10.1002/mrm.24765",
     [("radius", "15.0", "SMV kernel radius (mm)"), ("tik_reg", "1e-3", "Tikhonov regularization")]),
    ("pdf", "bfr", "pdf", "PDF",
     "Projection onto Dipole Fields: models the background field as external dipoles.",
     "Liu et al., NMR Biomed 2011", "10.1002/nbm.1670",
     [("tol", "1e-4", "convergence tolerance")]),
    ("lbv", "bfr", "lbv", "LBV",
     "Laplacian Boundary Value: solves the Laplacian of the field with boundary conditions.",
     "Zhou et al., NMR Biomed 2014", "10.1002/nbm.3064",
     [("tol", "1e-4", "convergence tolerance")]),
    ("ismv", "bfr", "ismv", "iSMV",
     "Iterative Spherical Mean Value background field removal.",
     "Wen et al., 2014", None,
     [("tol", "1e-4", "tolerance"), ("max_iter", "100", "iterations"), ("radius_factor", "2.0", "× max voxel size")]),
    # NOTE: HARPERELLA / iHARPERELLA are phase-domain (consume WRAPPED PHASE, not total field, and
    # take no B0 direction) — an `unwrap+bfr` span over single-echo phase. They need a bespoke run.sh
    # (echo selection), so they're excluded from this generator for now. TODO: add as a span.
    # --- dipole inversion ---
    ("rts", "dipole", "rts", "RTS",
     "Rapid Two-Step QSM: streaking-artifact reduction via a fast ADMM split.",
     "Kames et al., NeuroImage 2018", "10.1016/j.neuroimage.2018.07.043",
     [("delta", "1.0", "regularization"), ("mu", "1.0", "smoothness"), ("max_iter", "1000", "iterations")]),
    ("tv", "dipole", "tv", "TV (ADMM)",
     "Total Variation regularized dipole inversion solved with ADMM.",
     "Bilgic et al., 2014", None,
     [("lambda", "1e-4", "TV regularization"), ("rho", "1.0", "ADMM penalty"), ("max_iter", "1000", "iterations")]),
    ("tkd", "dipole", "tkd", "TKD",
     "Thresholded K-space Division: direct inversion with the dipole kernel thresholded.",
     "Shmueli et al., Magn Reson Med 2009", None,
     [("threshold", "0.1", "k-space threshold")]),
    ("tsvd", "dipole", "tsvd", "TSVD",
     "Truncated Singular Value Decomposition inversion.",
     "Wharton et al., Magn Reson Med 2010", "10.1002/mrm.22334",
     [("threshold", "0.1", "singular-value threshold")]),
    # NOTE: TGV is single-step (phase -> chi, doing unwrap+BFR+inversion itself); it is NOT a
    # standalone dipole inversion, so running it on a background-removed local field is wrong.
    # Excluded here — it belongs as an `end-to-end` span (phase -> chimap). TODO.
    ("tikhonov", "dipole", "tikhonov", "Tikhonov",
     "Closed-form L2 (Tikhonov) regularized inversion.",
     "Kames et al., 2018", None,
     [("lambda", "1e-4", "L2 regularization")]),
    ("nltv", "dipole", "nltv", "NLTV",
     "Nonlocal Total Variation regularized inversion.",
     "—", None,
     [("lambda", "1e-4", "regularization"), ("max_iter", "1000", "iterations")]),
    ("medi", "dipole", "medi", "MEDI",
     "Morphology Enabled Dipole Inversion: magnitude-guided edge regularization.",
     "Liu et al., 2012", None,
     [("lambda", "1e-4", "regularization"), ("percentage", "0.95", "edge percentage")]),
    ("ilsqr", "dipole", "ilsqr", "iLSQR",
     "Iterative LSQR inversion with streaking-artifact reduction.",
     "Li et al., NMR Biomed 2015", None,
     [("tol", "1e-4", "tolerance"), ("max_iter", "1000", "iterations")]),
]

def yamllist(items):
    return "".join(f"  - name: {n}\n    default: {d}\n    description: {desc}\n" for n, d, desc in items)


def param_block(algo, params):
    """Bash that reads parameter overrides from /input/config.json into $SET (empty if none).

    qsm-ci writes config.json from `--set name=value`; each declared param maps to the qsmxt flag
    `--<algo>-<name>`. Absent file/keys => the qsmxt binary defaults are used (CI is unaffected).
    """
    if not params:
        return "", ""
    lines = ["", "# Parameter overrides (qsm-ci run --set NAME=VALUE) arrive as /input/config.json.",
             'SET=""', 'CFG="$IN/config.json"', 'if [ -f "$CFG" ]; then']
    for n, _, _ in params:
        flag = f"--{algo}-{n.replace('_', '-')}"
        lines.append(f'  V=$(jq -r \'.{n} // empty\' "$CFG"); [ -n "$V" ] && SET="$SET {flag} $V"')
    lines.append("fi")
    return "\n".join(lines) + "\n", " $SET"


def run_sh(name, stage, group, algo, inp, out, slug, params):
    pblock, suffix = param_block(algo, params)
    cmd = (f'qsmxt {group} {algo} "$IN/{inp}.nii.gz" -m "$IN/mask.nii.gz" '
           f'-o "$OUT/{out}.nii.gz" --b0-direction $B0')
    if slug == "medi":  # MEDI: radians (needs B0+TE), uses magnitude, no internal SMV
        cmd += (' --field-strength "$(jq -r .B0 "$IN/params.json")"'
                ' --echo-time "$(jq -r .TE[0] "$IN/params.json")"'
                ' --smv false --magnitude "$IN/magnitude.nii.gz"')
    return ("#!/usr/bin/env bash\n"
            f"# QSM-CI submission — {name} ({stage} stage) via QSMxT / QSM.rs.\n"
            "set -euo pipefail\n"
            'IN="${1:-/input}"; OUT="${2:-/output}"\n'
            "B0=$(jq -r '.B0_dir | join(\" \")' \"$IN/params.json\")\n"
            f"{pblock}{cmd}{suffix}\n")


def gen(slug, stage, algo, name, desc, cite, doi, params):
    inp, out, group = STAGE[stage]
    d = ROOT / "algorithms" / slug
    d.mkdir(parents=True, exist_ok=True)

    # Single manifest: docs + runtime in one file. Code (run.sh) is mounted at /algo.
    (d / "algorithm.yml").write_text(
        f"name: {name}\nslug: {slug}\nstage: {stage}\nengine: QSMxT / QSM.rs\n"
        f"description: >\n  {desc}\n"
        f"citation: {cite if cite else 'null'}\n"
        f"doi: {doi if doi else 'null'}\n"
        f"code_url: {QSM_RS}\n"
        f"license: MIT\n"
        f"image: {IMAGE}\nrun: bash run.sh\n"
        f"parameters:\n{yamllist(params)}")

    (d / "run.sh").write_text(run_sh(name, stage, group, algo, inp, out, slug, params))
    (d / "run.sh").chmod((d / "run.sh").stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

    ptab = "\n".join(f"| `{n}` | {dv} | {ds} |" for n, dv, ds in params) or "| — | — | — |"
    (d / "README.md").write_text(
        f"# {name}\n\n{desc}\n\n"
        f"- **Stage:** `{stage}` ({inp} → {out}, ppm)\n"
        f"- **Engine:** [QSMxT]({QSMXT}) — the [QSM.rs]({QSM_RS}) Rust implementation\n"
        f"- **Reference:** {cite if cite else '_TODO_'}{f' · doi:[{doi}](https://doi.org/{doi})' if doi else ' _(DOI: TODO — verify)_'}\n\n"
        f"## How QSM-CI runs it\n\n```bash\nqsmxt {group} {algo} /input/{inp}.nii.gz -m /input/mask.nii.gz "
        f"-o /output/{out}.nii.gz --b0-direction <B0>\n```\n\n"
        f"## Parameters\n\n| parameter | default | description |\n|---|---|---|\n{ptab}\n\n"
        f"_Citations/DOIs are auto-generated best-effort references and should be verified._\n")
    return slug


def main():
    made = [gen(*a) for a in ALGOS]
    print(f"generated {len(made)} submissions:", ", ".join(made))


if __name__ == "__main__":
    main()
