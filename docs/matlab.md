# Submitting a MATLAB algorithm

MATLAB QSM code is welcome. You do **not** need a MATLAB license to submit — compile your code with
the MATLAB Compiler and run it on the free MATLAB Runtime, using the Neurodesk `matlabmcr` base
(the same approach Neurodesk uses for CAT12, etc.).

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

## Notes

- No network at run time — the MATLAB Runtime and all toolboxes must be inside the image.
- Keep to the [contract](../CONTRACT.md): one `chimap.nii.gz`, ppm, within the mask.
- See the Neurodesk `matlabmcr` template for the exact runtime versions and environment variables:
  `~/repos/neurodesk/neurocontainers/builder/templates/matlabmcr.yaml`.
