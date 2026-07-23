# Building hd-qsm (compiled MATLAB → MATLAB Runtime)

Compile `recon.m` on a machine with **MATLAB + MATLAB Compiler** (R2026a). Runs license-free on the
MATLAB Runtime. Same patterns as `matlab-tkd` (bundled NIfTI toolbox, OS gzip), plus the **HD-QSM**
code (`HDQSM.m`) **and** Carlos Milovic's **FANSI toolbox** — `HDQSM.m` calls FANSI's
`gradient_calc` and uses a FANSI dipole-kernel function, so FANSI must be on the compile path too.

Stage: `dipole` — consumes `localfield` (ppm), `mask`, `params`; two-stage L1→L2 linear inversion
(`HDQSM`) → `chimap` (ppm).

> **Own image** (NOT shared with the FANSI family): `ghcr.io/astewartau/qsm-ci/hd-qsm:v1`.

## 1. Fetch build-time deps (not committed)
```bash
cp -r /path/to/NIfTI_20140122               algorithms/hd-qsm/nifti   # Jimmy Shen toolbox
git clone https://github.com/mglambert/HD-QSM  algorithms/hd-qsm/hdqsm  # HD-QSM (HDQSM.m)
git clone https://gitlab.com/cmilovic/FANSI-toolbox algorithms/hd-qsm/fansi   # FANSI (gradient_calc, kernel)
```
> NOTE: the repo is **`mglambert/HD-QSM`** (with a hyphen) — `mglambert/HDQSM` returns 404.

## 2. Compile
```bash
cd algorithms/hd-qsm
matlab -batch "addpath('nifti'); addpath('hdqsm'); addpath(genpath('fansi')); mcc('-m','recon.m','-o','recon','-d','.')"   # -> ./recon
```
`mcc` traces `HDQSM`, `gradient_calc`, `dipole_kernel_angulated` and their deps.

## 3. Bake the MCR image and push
```bash
docker build -t ghcr.io/astewartau/qsm-ci/hd-qsm:v1 .   # FROM matlab-runtime:r2026a + COPY recon
docker push  ghcr.io/astewartau/qsm-ci/hd-qsm:v1
```
Then make the GHCR package public.

## Units
`localfield` is ppm; HD-QSM is a **linear** inversion (`real(ifftn(kernel.*Fx))`, no `sin`/`exp`),
so it is scale-linear — output susceptibility is in the same units as the input field. `recon.m`
feeds the ppm local field directly and writes a ppm `chimap`; **no radian conversion** is needed
(unlike the FANSI nonlinear methods). `alphaL2` is calibrated to this ppm (B0-normalized) scale,
matching the `HDQSM.m` example (`params.input = phase_use/phase_scale`).

## License
HD-QSM ships an **MIT** LICENSE (github.com/mglambert/HD-QSM); recorded in `algorithm.yml`.

> No MATLAB Compiler license? See Option B in [`docs/matlab.md`](../../docs/matlab.md).
