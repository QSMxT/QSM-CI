# Building fansi (compiled MATLAB → MATLAB Runtime)

Compile `recon.m` on a machine with **MATLAB + MATLAB Compiler** (R2026a). The result runs
license-free on the MATLAB Runtime. Same patterns as `matlab-tkd` (bundled NIfTI toolbox, OS
gzip; see `../matlab-tkd/BUILD.md`), plus Carlos Milovic's **FANSI toolbox**.

Stage: `dipole` — consumes `localfield` (ppm), `mask`, `params`; nonlinear TV/TGV ADMM inversion
(`nlTV`/`nlTGV`) → `chimap` (ppm).

> **Shared image.** `fansi`, `ndi`, `l1-qsm` and `wh-qsm` are all built from the one FANSI toolbox.
> They share the image tag `ghcr.io/astewartau/qsm-ci/fansi:v1`. `mcc` bundles the traced FANSI
> functions into each `recon` binary, so the toolbox is a *build-time* dependency only and does not
> need to live in the runtime image. If you compile all four, build one image per submission (each
> COPYs its own `recon`) or bake all four binaries into the single shared image under distinct
> names and point each `algorithm.yml`'s `run.sh` at the right one.

## 1. Fetch build-time deps (not committed)
```bash
cp -r /path/to/NIfTI_20140122               algorithms/fansi/nifti   # Jimmy Shen toolbox
git clone https://gitlab.com/cmilovic/FANSI-toolbox algorithms/fansi/fansi   # FANSI toolbox
```

## 2. Compile
```bash
cd algorithms/fansi
matlab -batch "addpath('nifti'); addpath(genpath('fansi')); mcc('-m','recon.m','-o','recon','-d','.')"   # -> ./recon
```
`mcc` traces only the FANSI functions `recon.m` actually calls (`nlTV`/`nlTGV`,
`dipole_kernel_angulated` and their deps); the GUI/metric/script files in `fansi/` are ignored.

## 3. Bake the MCR image and push
```bash
docker build -t ghcr.io/astewartau/qsm-ci/fansi:v1 .   # FROM matlab-runtime:r2026a + COPY recon
docker push  ghcr.io/astewartau/qsm-ci/fansi:v1
```
Then make the GHCR package public. QSM-CI runs `/opt/qsm-ci/recon /input /output` on the free
Runtime, offline.

## Units
`localfield` is ppm; FANSI's *nonlinear* solvers work in radians (they contain a `sin(phi-phase)`
data term). `recon.m` converts `phase_rad = field * 2*pi*42.58*B0*TE` and divides the output by the
same `phs_scale` to return ppm — exactly as the toolbox's `script_qsmchallenge.m` does. Any TE
cancels because the method is (nonlinearly) scale-consistent between input and output; a real
B0/TE is used only so the radian magnitude sits in the solver's well-conditioned range.

> No MATLAB Compiler license? You can't compile — run raw `.m` on a run-time-licensed MATLAB base
> instead (Option B in [`docs/matlab.md`](../../docs/matlab.md)). Compiling is strongly preferred.
