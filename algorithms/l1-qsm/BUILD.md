# Building l1-qsm (compiled MATLAB → MATLAB Runtime)

Compile `recon.m` on a machine with **MATLAB + MATLAB Compiler** (R2026a). Runs license-free on the
MATLAB Runtime. Same patterns as `matlab-tkd` (bundled NIfTI toolbox, OS gzip), plus Carlos
Milovic's **FANSI toolbox** (`nlL1TV.m` and its deps).

Stage: `dipole` — consumes `localfield` (ppm), `mask`, `params`; nonlinear L1-fidelity + TV ADMM
inversion (`nlL1TV`) → `chimap` (ppm).

> **Shared image.** `l1-qsm` shares `ghcr.io/astewartau/qsm-ci/fansi:v1` with `fansi`, `ndi`,
> `wh-qsm` (all one FANSI toolbox). `mcc` bundles the traced functions into `recon`, so the toolbox
> is build-time only. Build one image per submission (each COPYs its own `recon`) or bake all four
> binaries under distinct names into the single shared image. See `../fansi/BUILD.md`.

## 1. Fetch build-time deps (not committed)
```bash
cp -r /path/to/NIfTI_20140122               algorithms/l1-qsm/nifti   # Jimmy Shen toolbox
git clone https://gitlab.com/cmilovic/FANSI-toolbox algorithms/l1-qsm/fansi   # FANSI toolbox
```

## 2. Compile
```bash
cd algorithms/l1-qsm
matlab -batch "addpath('nifti'); addpath(genpath('fansi')); mcc('-m','recon.m','-o','recon','-d','.')"   # -> ./recon
```

## 3. Bake the MCR image and push
```bash
docker build -t ghcr.io/astewartau/qsm-ci/fansi:v1 .
docker push  ghcr.io/astewartau/qsm-ci/fansi:v1
```
Then make the GHCR package public.

## Units
`localfield` is ppm; `nlL1TV.m` works in radians (it forms `exp(1i*input)`). `recon.m` converts
`phase_rad = field * 2*pi*42.58*B0*TE` and divides the output by the same `phs_scale` to return ppm.
The L1 fidelity weight is `lambda*mask`; `lambda<1` rejects more inconsistent voxels (see nlL1TV.m).

> No MATLAB Compiler license? See Option B in [`docs/matlab.md`](../../docs/matlab.md).
