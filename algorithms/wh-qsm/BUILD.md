# Building wh-qsm (compiled MATLAB → MATLAB Runtime)

Compile `recon.m` on a machine with **MATLAB + MATLAB Compiler** (R2026a). Runs license-free on the
MATLAB Runtime. Same patterns as `matlab-tkd` (bundled NIfTI toolbox, OS gzip), plus Carlos
Milovic's **FANSI toolbox** (`WH_nlTV.m` and its deps).

Stage: `dipole` — consumes `localfield` (ppm), `mask`, `params`; joint susceptibility + residual
harmonic-field inversion (`WH_nlTV`) → `chimap` (ppm).

> **Why `dipole`, not `bfr+dipole`.** WH-QSM consumes the **local** field and removes only the
> *residual/remnant* background field left over after BFR, jointly with the inversion (see the
> `WH_nlTV.m` header: "remove background field remnants from *local* field maps and calculate the
> susceptibility of tissues simultaneously"). It is not a full background-field-removal step and
> does not take the total field, so it belongs at the `dipole` stage.

> **Shared image.** `wh-qsm` shares `ghcr.io/astewartau/qsm-ci/fansi:v1` with `fansi`, `ndi`,
> `l1-qsm` (all one FANSI toolbox). `mcc` bundles the traced functions into `recon`, so the toolbox
> is build-time only. Build one image per submission (each COPYs its own `recon`) or bake all four
> binaries under distinct names into the single shared image. See `../fansi/BUILD.md`.

## 1. Fetch build-time deps (not committed)
```bash
cp -r /path/to/NIfTI_20140122               algorithms/wh-qsm/nifti   # Jimmy Shen toolbox
git clone https://gitlab.com/cmilovic/FANSI-toolbox algorithms/wh-qsm/fansi   # FANSI toolbox
```

## 2. Compile
```bash
cd algorithms/wh-qsm
matlab -batch "addpath('nifti'); addpath(genpath('fansi')); mcc('-m','recon.m','-o','recon','-d','.')"   # -> ./recon
```

## 3. Bake the MCR image and push
```bash
docker build -t ghcr.io/astewartau/qsm-ci/fansi:v1 .
docker push  ghcr.io/astewartau/qsm-ci/fansi:v1
```
Then make the GHCR package public.

## Units
`localfield` is ppm; `WH_nlTV.m` works in radians (nonlinear `sin` data term). `recon.m` converts
`phase_rad = field * 2*pi*42.58*B0*TE` and divides the susceptibility output by the same `phs_scale`
to return ppm.

> No MATLAB Compiler license? See Option B in [`docs/matlab.md`](../../docs/matlab.md).
