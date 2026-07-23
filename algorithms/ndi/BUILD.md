# Building ndi (compiled MATLAB → MATLAB Runtime)

Compile `recon.m` on a machine with **MATLAB + MATLAB Compiler** (R2026a). Runs license-free on the
MATLAB Runtime. Same patterns as `matlab-tkd` (bundled NIfTI toolbox, OS gzip), plus Carlos
Milovic's **FANSI toolbox** (`ndi.m` and its deps).

Stage: `dipole` — consumes `localfield` (ppm), `mask`, `params`; nonlinear gradient-descent
inversion (`ndi`) → `chimap` (ppm).

> **Shared image.** `ndi` shares `ghcr.io/astewartau/qsm-ci/fansi:v1` with `fansi`, `l1-qsm`,
> `wh-qsm` (all one FANSI toolbox). `mcc` bundles the traced FANSI functions into `recon`, so the
> toolbox is build-time only. Either build one image per submission (each COPYs its own `recon`) or
> bake all four binaries under distinct names into the single shared image. See `../fansi/BUILD.md`.

## 1. Fetch build-time deps (not committed)
```bash
cp -r /path/to/NIfTI_20140122               algorithms/ndi/nifti   # Jimmy Shen toolbox
git clone https://gitlab.com/cmilovic/FANSI-toolbox algorithms/ndi/fansi   # FANSI toolbox
```

## 2. Compile
```bash
cd algorithms/ndi
matlab -batch "addpath('nifti'); addpath(genpath('fansi')); mcc('-m','recon.m','-o','recon','-d','.')"   # -> ./recon
```
`mcc` traces `ndi`, `susc2field`, `dipole_kernel_angulated` and their deps.

## 3. Bake the MCR image and push
```bash
docker build -t ghcr.io/astewartau/qsm-ci/fansi:v1 .
docker push  ghcr.io/astewartau/qsm-ci/fansi:v1
```
Then make the GHCR package public.

## Units
`localfield` is ppm; `ndi.m` works in radians (nonlinear `sin` data term). `recon.m` converts
`phase_rad = field * 2*pi*42.58*B0*TE` and divides the output by the same `phs_scale` to return
ppm, per the `ndi.m` header ("input/output in radians").

> No MATLAB Compiler license? See Option B in [`docs/matlab.md`](../../docs/matlab.md).
