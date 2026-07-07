# Submitting a MATLAB algorithm

MATLAB QSM code is welcome. **You provide `.m` code + an environment; you don't bake an image**
(see [../CONTRACT.md](../CONTRACT.md)) — your scripts are mounted at `/algo`, and any toolbox is
downloaded during the build phase (which has network). The only real question is *what runs your
`.m` at run time*, because the run phase is offline:

- **Octave** (Option C, recommended) — runs `.m` **license-free**, offline, no problem. Download an
  Octave-compatible toolbox at build, mount your code, done. This is how
  [`octave-tkd`](../algorithms/octave-tkd) works today.
- **Full MATLAB base + toolbox** (Option A) — a licensed MATLAB container *can* run raw `.m` + a
  downloaded toolbox (SEPIA/MEDI/…) with **no compilation**. The catch is **licensing at run time**:
  the offline run phase can't reach a network license server, so you need a license the runner can
  use offline (a baked/mounted license file, or a self-hosted runner with one configured).
- **MATLAB Runtime / MCR** (Option A′) — license-free *at run time*, but MCR only runs **compiled**
  code, so you `mcc`-compile your wrapper+toolbox once (license at build). Good when you can't provide
  a run-time MATLAB license.

So: downloading the toolbox and mounting your code is exactly right — Octave runs it free; full
MATLAB runs it too but needs a run-time license; MCR is the license-free-but-compile middle path.

> Neurodesk ships no ready MATLAB *QSM* container (its QSM tools — QSMxT, TGV-QSM, CLEARSWI, ROMEO —
> are Python/Julia; its `matlabmcr` images are CAT12, Brainstorm, …). You supply the environment via
> `image:` or a small `Dockerfile`.

## Option A — full MATLAB base + downloaded toolbox + mounted `.m`

This is the "download the toolbox and use it with a regular MATLAB container" path. Your `Dockerfile`
starts from a licensed MATLAB base and downloads the toolbox during the build (network on); your
`.m` code is mounted at `/algo` at run time — nothing is compiled or baked.

```dockerfile
# Environment only — no algorithm code copied in (it is mounted at /algo).
FROM containers.mathworks.com/matlab:r2023b        # a licensed MATLAB base
RUN git clone --depth 1 https://github.com/kschan0214/sepia /opt/sepia   # download at build
```

`run.sh` (mounted with your code):

```bash
#!/usr/bin/env bash
set -euo pipefail
IN="${1:-/input}"; OUT="${2:-/output}"
matlab -batch "addpath(genpath('/opt/sepia')); addpath('/algo'); recon('$IN','$OUT')"
```

**Licensing caveat:** the run phase is offline (`--network none`), so a full MATLAB base needs a
license it can use **without** a network license server — a baked/mounted license file, or a
self-hosted runner configured with one. If you can't provide that, use Option A′ or Octave.

## Option A′ — MATLAB Runtime (MCR), license-free at run time

MCR runs only **compiled** code, so compile once on a machine with MATLAB + Compiler, then run the
binary on the free Runtime (no run-time license). The compiled `recon` is your mounted code.

```matlab
mcc -m recon.m -o recon        % produces the standalone `recon` (+ MCR wrapper)
```

```dockerfile
FROM containers.mathworks.com/matlab-runtime:r2023b   # free MATLAB Runtime, matching version
```

`run.sh` runs `/algo/recon /input /output` (the MCR wrapper sets `LD_LIBRARY_PATH`). Read/write
NIfTI with `niftiread`/`niftiwrite` or a bundled toolbox; output **ppm** on the `mask.nii.gz` grid.
See [`algorithms/matlab-tkd`](../algorithms/matlab-tkd) for the template.

## Option B — reuse an existing Neurodesk QSM container

If your method is already in a Neurodesk container (e.g. QSMxT, TGV-QSM), point `image:` at that
container and write a thin `run.sh` that maps `/input`/`/output` onto its CLI. This is often the
fastest path.

## Option C — GNU Octave (license-free, recommended for self-contained code)

Run your `.m` code on Octave — no MATLAB license, builds in seconds. See the working reference
[`algorithms/octave-tkd`](../algorithms/octave-tkd): `recon.m` plus a tiny self-contained
`readnii.m`/`writenii.m` (NIfTI-1, no toolbox). Its scores match the Python reference exactly.

```dockerfile
FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends octave gzip && rm -rf /var/lib/apt/lists/*
COPY recon.m readnii.m writenii.m run.sh /opt/algo/
WORKDIR /opt/algo
```

`run.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail
IN="${1:-/input}"; OUT="${2:-/output}"
DIR="$(cd "$(dirname "$0")" && pwd)"
octave --no-gui -q --eval "cd('$DIR'); recon('$IN','$OUT')"
```

Caveats: Octave covers core MATLAB and common functions, but not proprietary toolboxes (Image
Processing, Optimization, …) or `niftiread`/`niftiwrite`. If your method needs those, use Option A.

## Notes

- No network at run time — the MATLAB Runtime and all toolboxes must be inside the image.
- Keep to the [contract](../CONTRACT.md): one `chimap.nii.gz`, ppm, within the mask.
- See the Neurodesk `matlabmcr` template for the exact runtime versions and environment variables:
  `~/repos/neurodesk/neurocontainers/builder/templates/matlabmcr.yaml`.
