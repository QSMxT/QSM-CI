# Submitting a MATLAB algorithm

MATLAB QSM code is welcome, and you do **not** need a MATLAB license to submit. There are three
routes, in rough order of ease:

- **Octave** (Option C) — run your `.m` code license-free on GNU Octave. Best for self-contained
  code (no proprietary toolboxes). This is how the reference [`octave-tkd`](../algorithms/octave-tkd)
  submission works, and it runs today with no license at all.
- **MATLAB Runtime** (Option A) — compile with the MATLAB Compiler (`mcc`, needs a license once at
  build time) and run the compiled binary on the free MATLAB Runtime via the Neurodesk `matlabmcr`
  base. Best for MATLAB toolboxes (SEPIA, MEDI, STI Suite, chi-separation).
- **Wrap an existing container** (Option B).

> Note: Neurodesk does not currently ship a ready-made MATLAB *QSM* container — its QSM tools
> (QSMxT, TGV-QSM, CLEARSWI, ROMEO) are Python/Julia, and its `matlabmcr`-based containers are other
> tools (CAT12, Brainstorm, …). So for a MATLAB QSM method you package it yourself via Option A or C.

## Option A — compiled MATLAB on the MATLAB Runtime (recommended)

1. On a machine with MATLAB + MATLAB Compiler, compile your entry point:

   ```matlab
   % recon.m:  function recon(inputDir, outputDir)
   %   reads <inputDir>/phase.nii.gz etc., writes <outputDir>/chimap.nii.gz (ppm)
   mcc -m recon.m -o recon
   ```

2. Build an image from a MATLAB Runtime base and copy in the compiled binary:

   ```dockerfile
   # Base with the matching MATLAB Runtime (see Neurodesk matlabmcr recipe for versions)
   FROM containers.mathworks.com/matlab-runtime:r2023b
   COPY recon /opt/recon
   COPY run.sh /opt/run.sh
   WORKDIR /opt
   ```

   `run.sh`:

   ```bash
   #!/usr/bin/env bash
   set -euo pipefail
   ./recon /input /output    # the MCR wrapper sets up LD_LIBRARY_PATH
   ```

3. Read/write NIfTI in MATLAB with `niftiread` / `niftiwrite` (or a bundled toolbox). Output must be
   **ppm** on the same grid as `mask.nii.gz`.

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
