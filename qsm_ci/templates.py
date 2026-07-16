"""Submission file templates — the starters `qsm-ci new` scaffolds.

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


# A `magnitude` read, injected only into stages that consume it (dipole, bfr+dipole) — where a
# method might use it for data-fidelity weighting. Every other consumed artifact (primary input,
# mask, params) is the same across stages and is read unconditionally in the templates below.
_MAG = {
    "python": '    magnitude = nib.load(f"{inp}/magnitude.nii.gz").get_fdata()  # e.g. data-fidelity weighting\n',
    "julia": '    magnitude = niread(joinpath(inp, "magnitude.nii.gz")).raw  # e.g. data-fidelity weighting\n',
    "matlab": "    magnitude = double(niftiread(fullfile(inp, 'magnitude.nii.gz')));  % e.g. data-fidelity weighting\n",
    "rust": ('    let magnitude = ReaderOptions::new()\n'
             '        .read_file(format!("{}/magnitude.nii.gz", inp))?\n'
             '        .into_volume().into_ndarray::<f64>()?; // e.g. data-fidelity weighting\n'),
}


def _mag(stage: str, lang: str) -> str:
    return _MAG[lang] if "magnitude" in STAGES[stage]["consumes"] else ""


def _sub(text: str, stage: str, name: str, lang: str) -> str:
    return (text
            .replace("__NAME__", name)
            .replace("__STAGE__", stage)
            .replace("__C__", CONSUMES[stage])
            .replace("__MAG__", _mag(stage, lang))
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
    # This __STAGE__ stage consumes: __C__  (all in `inp`), and must write __OUT__.nii.gz to `out`.
    img = nib.load(f"{inp}/__INP__.nii.gz")            # primary input (ppm)
    __INP__ = img.get_fdata().astype(np.float64)
    mask = nib.load(f"{inp}/mask.nii.gz").get_fdata() > 0.5

    # Acquisition parameters. B0_dir is the unit B0 direction in image space (key for dipole/BFR);
    # also params["voxel_size"] (mm), params["B0"] (tesla), params["TE"] (echo times, s).
    params = json.load(open(f"{inp}/params.json"))
    b0_dir = np.array(params["B0_dir"], float)
__MAG__
    # Optional parameter overrides (qsm-ci run --set NAME=VALUE); declare them in algorithm.yml.
    cfg = json.load(open(f"{inp}/config.json")) if os.path.exists(f"{inp}/config.json") else {}
    # e.g. threshold = cfg.get("threshold", 0.1)

    # TODO: your reconstruction here. Produce __OUT__ (ppm), within the mask.
    __OUT__ = __INP__ * mask  # placeholder

    nib.save(nib.Nifti1Image(__OUT__.astype(np.float32), img.affine), f"{out}/__OUT__.nii.gz")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
'''

_JULIA = '''# __NAME__ — __STAGE__ stage.  consumes: __C__  (all in `inp`); writes __OUT__.nii.gz to `out`.
using NIfTI

function main(inp, out)
    img = niread(joinpath(inp, "__INP__.nii.gz"))     # primary input (ppm)
    __INP__ = Float64.(img.raw)
    mask = niread(joinpath(inp, "mask.nii.gz")).raw .> 0.5

    # params.json (B0_dir = unit B0 direction, voxel_size mm, B0 tesla, TE echo times s) is in `inp`;
    # add JSON.jl to your image to parse it if your method needs those (e.g. B0_dir for dipole/BFR).
__MAG__
    # TODO: your reconstruction here. Produce __OUT__ (ppm), within the mask.
    __OUT__ = __INP__ .* mask  # placeholder

    niwrite(joinpath(out, "__OUT__.nii.gz"), NIVolume(img.header, Float32.(__OUT__)))
end

main(ARGS[1], ARGS[2])
'''

_MATLAB = '''function recon(inp, out)
% __NAME__ — __STAGE__ stage.  consumes: __C__  (all in inp); writes __OUT__.nii.gz to out.
    info = niftiinfo(fullfile(inp, '__INP__.nii.gz'));   % primary input (ppm)
    __INP__ = double(niftiread(info));
    mask = niftiread(fullfile(inp, 'mask.nii.gz')) > 0.5;

    % Acquisition parameters. p.B0_dir = unit B0 direction (key for dipole/BFR);
    % also p.voxel_size (mm), p.B0 (tesla), p.TE (echo times, s).
    p = jsondecode(fileread(fullfile(inp, 'params.json')));
    b0_dir = p.B0_dir(:)';
__MAG__
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

    // This __STAGE__ stage consumes: __C__  (all in `inp`); writes __OUT__.nii.gz to `out`.
    let obj = ReaderOptions::new().read_file(format!("{}/__INP__.nii.gz", inp))?; // primary (ppm)
    let header = obj.header().clone();
    let __INP__ = obj.into_volume().into_ndarray::<f64>()?;
    let mask = ReaderOptions::new()
        .read_file(format!("{}/mask.nii.gz", inp))?
        .into_volume().into_ndarray::<f64>()?
        .mapv(|v| if v > 0.5 { 1.0 } else { 0.0 });
    // params.json (B0_dir = unit B0 direction, voxel_size mm, B0 tesla, TE echo times s) is at
    // {inp}/params.json; add serde_json to Cargo.toml to parse it (e.g. B0_dir for dipole/BFR).
__MAG__
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

You compile `recon.m` yourself, once, on a machine with **MATLAB + MATLAB Compiler** — the only place
a license is needed, at *build* time. The standalone binary then runs on the free **MATLAB Runtime
(MCR)**, so QSM-CI scores it offline with no license. (QSM-CI cannot compile it for you — its build
environment has no MATLAB license.)

## 1. Compile

```bash
matlab -batch "mcc('-m','recon.m','-o','recon','-d','.')"   # -> ./recon (needs MATLAB + Compiler)
```

## 2. Bake the MCR image and push

```dockerfile
FROM containers.mathworks.com/matlab-runtime:__RUNTIME__   # free Runtime; match the compiler release
ENV AGREE_TO_MATLAB_RUNTIME_LICENSE=yes
COPY recon /opt/qsm-ci/recon
RUN chmod +x /opt/qsm-ci/recon
```

```bash
docker build -t <your-image:tag> .  &&  docker push <your-image:tag>   # then make the package public
```

Point `algorithm.yml`'s `image:` at that tag. QSM-CI runs `/opt/qsm-ci/recon /input /output` on the
free Runtime, offline.

## What goes in your PR

**Only text files:** `algorithm.yml`, `run.sh`, `recon.m` (your source, for review), and this
`BUILD.md`. The compiled binary is **not** committed to git — it lives inside the image you pushed
above, and QSM-CI pulls that image to run it. (This differs from Python/Julia/Rust, where your source
*is* what runs, inside a ready base image — no compile, no image to build or push.)

## Notes

- The Runtime version (`runtime:` in algorithm.yml — `__RUNTIME__`) **must** match the MATLAB Compiler
  release used to build `recon`.
- `mcc` bundles the toolbox code your method uses (SEPIA, MEDI, …) into the binary.
- At scoring time `run.sh` runs the compiled binary with `--network none` — no license, no network.
- **No MATLAB Compiler?** You can instead run raw `.m` on a run-time-licensed MATLAB base image — see
  the run-time-license option in [docs/matlab.md](https://github.com/QSMxT/QSM-CI/blob/main/docs/matlab.md).
  Compiling is strongly preferred.
'''


def _bash_extra_inputs(stage: str) -> str:
    """Extra input lines for the bash template — magnitude, for stages that consume it."""
    if "magnitude" in STAGES[stage]["consumes"]:
        return "\n#   magnitude.nii.gz          (magnitude; e.g. data-fidelity weighting)"
    return ""


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
                   '# See BUILD.md to compile recon.m and bake the MCR image.\n'
                   'BIN="${MATLAB_RECON:-/opt/qsm-ci/recon}"\n'
                   '[ -x "$BIN" ] || BIN="$HERE/recon"\n'
                   'exec "$BIN" "$IN" "$OUT"\n'),
        "rust": ('# Build your binary in the image (network is on at build time): cargo build --release\n'
                 'BIN="$HERE/target/release/recon"\n'
                 '[ -x "$BIN" ] || cargo build --release --offline --manifest-path "$HERE/Cargo.toml"\n'
                 '"$BIN" "$IN" "$OUT"\n'),
        "other": (
            f'# Minimal working example for the {stage} stage. Inputs are in "$IN":\n'
            f"#   {input_artifact(stage)}.nii.gz  (primary input, ppm){_bash_extra_inputs(stage)}\n"
            "#   mask.nii.gz                (brain mask)\n"
            "#   params.json               (B0_dir, voxel_size mm, B0 tesla, TE echo times s)\n"
            f'# You must write {produced_artifact(stage)}.nii.gz (ppm, within the mask) to "$OUT",\n'
            "# on the same voxel grid as the inputs.\n"
            "\n"
            "# Acquisition parameters are injected as env vars (no parsing needed):\n"
            '#   $QSMCI_B0 (tesla)  $QSMCI_TE (echoes)  $QSMCI_TE0 (first echo)\n'
            '#   $QSMCI_B0_DIR (e.g. dipole/BFR need this)  $QSMCI_VOXEL_SIZE (mm)\n'
            '#   $QSMCI_SET_<NAME>  for each  qsm-ci run --set NAME=VALUE  override\n'
            'echo "B0 direction: $QSMCI_B0_DIR"\n'
            "# (params.json / config.json are also in $IN if you prefer to read the JSON.)\n"
            "\n"
            "# TODO: replace this passthrough with your reconstruction — e.g. call your own program:\n"
            f'#   "$HERE/my-program" "$IN/{input_artifact(stage)}.nii.gz" "$IN/mask.nii.gz" "$OUT/{produced_artifact(stage)}.nii.gz"\n'
            f'cp "$IN/{input_artifact(stage)}.nii.gz" "$OUT/{produced_artifact(stage)}.nii.gz"   # placeholder: copies input through unchanged\n'),
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
        out.append((LANGS[lang]["file"], _sub(_RECON[lang], stage, name, lang)))
    if lang == "rust":
        out.append(("Cargo.toml", _CARGO))
    if lang == "matlab":
        out.append(("BUILD.md", _MATLAB_BUILD.replace("__NAME__", name).replace("__RUNTIME__", MATLAB_RUNTIME)))
    return out
