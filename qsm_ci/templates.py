"""Submission file templates — the same starters the web Submit wizard generates.

Keyed by stage (which artifact you read/write) and language. Token substitution (not f-strings)
keeps the Rust/MATLAB/Julia braces intact.
"""

from __future__ import annotations

from .stages import STAGES, input_artifact, produced_artifact

# stage -> human list of consumed artifacts (for comments)
CONSUMES = {s: ", ".join(STAGES[s]["consumes"]) for s in STAGES}

LANGS = {
    "python": {"name": "Python", "file": "recon.py", "image": "python:3.11 + numpy, nibabel"},
    "rust": {"name": "Rust", "file": "recon.rs", "image": "rust:1 (deps vendored at build)"},
    "matlab": {"name": "MATLAB (compiled)", "file": "recon.m", "image": "matlab-runtime (compiled once via MATLAB Compiler)"},
    "julia": {"name": "Julia", "file": "recon.jl", "image": "julia:1 + NIfTI.jl"},
    "other": {"name": "Other", "file": "run.sh", "image": "any base with your deps"},
}


def _sub(text: str, stage: str, name: str) -> str:
    return (text
            .replace("__NAME__", name)
            .replace("__STAGE__", stage)
            .replace("__C__", CONSUMES[stage])
            .replace("__INP__", input_artifact(stage))
            .replace("__OUT__", produced_artifact(stage)))


_PYTHON = '''#!/usr/bin/env python3
"""__NAME__ — __STAGE__ stage. Reads <in-dir>, writes <out-dir>."""
import json
import os
import sys
import nibabel as nib
import numpy as np


def main(inp, out):
    # consumes: __C__
    img = nib.load(f"{inp}/__INP__.nii.gz")
    __INP__ = img.get_fdata().astype(np.float64)
    mask = nib.load(f"{inp}/mask.nii.gz").get_fdata() > 0.5

    # Optional parameter overrides (qsm-ci run --set NAME=VALUE) arrive here; declare them in
    # algorithm.yml. Fall back to your own defaults.
    cfg = json.load(open(f"{inp}/config.json")) if os.path.exists(f"{inp}/config.json") else {}
    # e.g. threshold = cfg.get("threshold", 0.1)

    # TODO: your reconstruction here. Produce __OUT__ (ppm), within the mask.
    __OUT__ = __INP__ * mask  # placeholder

    nib.save(nib.Nifti1Image(__OUT__.astype(np.float32), img.affine), f"{out}/__OUT__.nii.gz")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
'''

_JULIA = '''# __NAME__ — __STAGE__ stage.  consumes: __C__
using NIfTI

function main(inp, out)
    img = niread(joinpath(inp, "__INP__.nii.gz"))
    __INP__ = Float64.(img.raw)
    mask = niread(joinpath(inp, "mask.nii.gz")).raw .> 0.5

    # TODO: your reconstruction here. Produce __OUT__ (ppm), within the mask.
    __OUT__ = __INP__ .* mask  # placeholder

    niwrite(joinpath(out, "__OUT__.nii.gz"), NIVolume(img.header, Float32.(__OUT__)))
end

main(ARGS[1], ARGS[2])
'''

_MATLAB = '''function recon(inp, out)
% __NAME__ — __STAGE__ stage.  consumes: __C__
    info = niftiinfo(fullfile(inp, '__INP__.nii.gz'));
    __INP__ = double(niftiread(info));
    mask = niftiread(fullfile(inp, 'mask.nii.gz')) > 0.5;

    % TODO: your reconstruction here. Produce __OUT__ (ppm), within the mask.
    __OUT__ = __INP__ .* mask;  % placeholder

    info.Datatype = 'single';
    niftiwrite(single(__OUT__), fullfile(out, '__OUT__.nii'), info, 'Compressed', true);
end
'''

_RUST = '''//! __NAME__ — __STAGE__ stage. Reads <in-dir>, writes <out-dir>.
use std::env;
use nifti::writer::WriterOptions;
use nifti::{IntoNdArray, NiftiObject, ReaderOptions};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args: Vec<String> = env::args().collect();
    let (inp, out) = (&args[1], &args[2]);

    // consumes: __C__
    let obj = ReaderOptions::new().read_file(format!("{}/__INP__.nii.gz", inp))?;
    let header = obj.header().clone();
    let __INP__ = obj.into_volume().into_ndarray::<f64>()?;
    let mask = ReaderOptions::new()
        .read_file(format!("{}/mask.nii.gz", inp))?
        .into_volume().into_ndarray::<f64>()?
        .mapv(|v| if v > 0.5 { 1.0 } else { 0.0 });

    // TODO: your reconstruction here. Produce __OUT__ (ppm), within the mask.
    let __OUT__ = &__INP__ * &mask; // placeholder

    WriterOptions::new(format!("{}/__OUT__.nii.gz", out))
        .reference_header(&header)
        .write_nifti(&__OUT__)?;
    Ok(())
}
'''

_CARGO = '''[package]
name = "recon"
version = "0.1.0"
edition = "2021"

[[bin]]
name = "recon"
path = "recon.rs"

[dependencies]
nifti = { version = "0.16", features = ["ndarray_volumes"] }
ndarray = "0.15"
'''

_RECON = {"python": _PYTHON, "julia": _JULIA, "matlab": _MATLAB, "rust": _RUST}

# Default MATLAB Runtime release for scaffolded MATLAB submissions.
MATLAB_RUNTIME = "r2026a"

_MATLAB_BUILD = '''# Building __NAME__ for the MATLAB Runtime

Compile `recon.m` once on a machine (or CI runner) with **MATLAB + MATLAB Compiler** — the only place
a license is needed. The result runs on the free **MATLAB Runtime (MCR)**, so QSM-CI scores it
offline with no license.

## Option A — let CI compile it (recommended)

Push just `recon.m`, then run
[`.github/workflows/matlab-compile.yml`](../../.github/workflows/matlab-compile.yml) on a self-hosted
runner that has MATLAB + Compiler + your license. It reads the `matlab:` block in `algorithm.yml`,
compiles `recon.m`, and pushes the image to the `image:` tag for you. `image:` is just the *intended*
tag — it does not need to exist beforehand.

## Option B — compile locally

```bash
matlab -batch "mcc('-m','recon.m','-o','recon','-d','.')"   # needs MATLAB + Compiler + license
```

Bake the compiled `recon` into an MCR image and push it to your `image:` tag:

```dockerfile
FROM containers.mathworks.com/matlab-runtime:__RUNTIME__   # free Runtime; match the compiler release
COPY recon /opt/qsm-ci/recon
RUN chmod +x /opt/qsm-ci/recon
```

## Notes

- The Runtime version (`runtime:` in algorithm.yml — `__RUNTIME__`) **must** match the MATLAB Compiler
  release used to build `recon`.
- `mcc` bundles the toolbox code your method uses (SEPIA, MEDI, …) into the binary.
- At scoring time `run.sh` runs the compiled binary with `--network none` — no license, no network.
'''


def _run_sh(stage: str, lang: str, name: str) -> str:
    head = ("#!/usr/bin/env bash\n"
            f"# {name} — {stage} stage.\n"
            f"# consumes: {CONSUMES[stage]}\n"
            f"# produces: {produced_artifact(stage)}.nii.gz (ppm, within the mask)\n"
            "# parameter overrides (qsm-ci run --set) arrive as $IN/config.json\n"
            'set -euo pipefail\n'
            'IN="${1:-/input}"; OUT="${2:-/output}"\n'
            'HERE="$(cd "$(dirname "$0")" && pwd)"\n\n')
    body = {
        "python": 'python3 "$HERE/recon.py" "$IN" "$OUT"\n',
        "julia": 'julia "$HERE/recon.jl" "$IN" "$OUT"\n',
        "matlab": ('# Runs the MATLAB-compiled `recon` on the free MATLAB Runtime (no license at run time).\n'
                   '# Baked into the image at /opt/qsm-ci/recon (recommended), or mounted at /algo/recon.\n'
                   '# See BUILD.md to compile recon.m (locally or via .github/workflows/matlab-compile.yml).\n'
                   'BIN="${MATLAB_RECON:-/opt/qsm-ci/recon}"\n'
                   '[ -x "$BIN" ] || BIN="$HERE/recon"\n'
                   'exec "$BIN" "$IN" "$OUT"\n'),
        "rust": ('# Build your binary in the image (network is on at build time): cargo build --release\n'
                 'BIN="$HERE/target/release/recon"\n'
                 '[ -x "$BIN" ] || cargo build --release --offline --manifest-path "$HERE/Cargo.toml"\n'
                 '"$BIN" "$IN" "$OUT"\n'),
        "other": (f"# TODO: run your reconstruction in whatever language you like.\n"
                  f"# Read {input_artifact(stage)}.nii.gz + mask.nii.gz from \"$IN\"; write "
                  f"{produced_artifact(stage)}.nii.gz (ppm,\n"
                  '# within the mask) to "$OUT". For example:\n'
                  '#   "$HERE/my-program" "$IN" "$OUT"\n'),
    }
    return head + body.get(lang, body["python"])


def algorithm_yml(meta: dict) -> str:
    """meta: name, slug, stage, description, authors(list[str]), citation, doi, code_url,
    license, image, run, params(list of (name, default, description))."""
    y = f"name: {meta['name']}\nslug: {meta['slug']}\nstage: {meta['stage']}\n"
    y += f"description: >\n  {meta.get('description') or 'TODO'}\n"
    authors = meta.get("authors") or []
    if authors:
        y += "authors:\n" + "".join(f"  - name: {a}\n" for a in authors)
    y += f"citation: {meta.get('citation') or 'null'}\n"
    y += f"doi: {meta.get('doi') or 'null'}\n"
    y += f"code_url: {meta.get('code_url') or 'null'}\n"
    y += f"license: {meta.get('license') or 'MIT'}\n"
    y += f"image: {meta.get('image') or 'ghcr.io/you/your-image:v1'}\n"
    y += f"run: {meta.get('run') or 'bash run.sh'}\n"
    if meta.get("lang") == "matlab":
        y += f"matlab:\n  entry: recon.m\n  runtime: {meta.get('matlab_runtime') or MATLAB_RUNTIME}\n"
    params = meta.get("params") or []
    if params:
        y += "parameters:\n" + "".join(
            f"  - name: {n}\n    default: {d}\n    description: {desc}\n" for n, d, desc in params)
    return y


def files(meta: dict) -> "list[tuple[str, str]]":
    """Return [(filename, body)] for a submission folder."""
    stage, lang, name = meta["stage"], meta.get("lang", "python"), meta["name"]
    out = [("algorithm.yml", algorithm_yml(meta)),
           ("run.sh", _run_sh(stage, lang, name))]
    if lang != "other":
        out.append((LANGS[lang]["file"], _sub(_RECON[lang], stage, name)))
    if lang == "rust":
        out.append(("Cargo.toml", _CARGO))
    if lang == "matlab":
        out.append(("BUILD.md", _MATLAB_BUILD.replace("__NAME__", name).replace("__RUNTIME__", MATLAB_RUNTIME)))
    return out
