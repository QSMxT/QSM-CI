# Building whqsm (compiled MATLAB → MATLAB Runtime)

Compile `recon.m` with **licensed MATLAB R2023b + MATLAB Compiler** and bake it onto the R2023b
MATLAB Runtime. R2023b because it is the licensed MATLAB the fidelity check runs on
([`../../fidelity/matlab/`](../../fidelity/matlab/README.md)), so the container and the reference
runs share one release. Bundled NIfTI toolbox and OS gzip (no JVM), plus the authors' **FANSI
toolbox at commit 93044a3** (gitlab.com/cmilovic/FANSI-toolbox), the commit QSM.rs's port
(`whqsm-qsmrs`) cites, with one QSM-CI patch to `WH_nlTV.m` (the Newton guard, below).

Stage: `dipole`. It consumes `localfield` (ppm), `mask`, `params`, runs `WH_nlTV.m` and writes `chimap` (ppm).

## 1. Fetch build-time deps (not committed)
```bash
git clone https://gitlab.com/cmilovic/FANSI-toolbox.git /tmp/fansi && git -C /tmp/fansi checkout 93044a3
cd algorithms/whqsm
cp -r /path/to/NIfTI_20140122 nifti
mkdir -p fansi && for f in Inversion/WH-QSM/WH_nlTV.m dipole_kernel_angulated.m; do cp /tmp/fansi/$f fansi/; done
patch --no-backup-if-mismatch fansi/WH_nlTV.m wh_nltv_newton_guard.patch
```
These are every FANSI file `recon.m` reaches. [`fidelity/config.sh`](fidelity/config.sh)
(`fid_assemble`) is the same recipe as a script.

## 2. Compile
```bash
matlab -batch "addpath('nifti'); addpath('fansi'); mcc('-m','recon.m','-o','recon','-d','.')"
```
Everything is plain `.m`, so mcc traces it all. Check that `unresolvedSymbols.txt` and
`mccExcludedFiles.log` list nothing. The harness does this compile as a Slurm job
(`submit.sh whqsm build`; log in `reports/build.txt`).

## 3. Bake the image and push
```bash
podman build -t ghcr.io/astewartau/qsm-ci/wh-qsm:v3 .   # needs ./recon from §2
podman push  ghcr.io/astewartau/qsm-ci/wh-qsm:v3
```
The package is public (its `v1` was QSM-CI's earlier, unchecked FANSI-family build; `v2` is
FANSI verbatim, without the Newton guard). Pin `image:` in
`algorithm.yml` by the pushed digest and rerun the fidelity check
([`fidelity/REPORT.md`](fidelity/REPORT.md)). Never overwrite a tag.

## Inputs, units and defaults
`recon.m` follows the FANSI toolbox's own example scripts:
- **Units.** FANSI works on the local phase in radians. The field is scaled by FANSI's
  `phs_scale = te·gyro·B0`, `gyro = 2π·42.58` (`script_invivo.m:58-62`), and χ = `out.x/phs_scale`.
  `te` is the first echo time, QSM.rs's default for this method; `script_DICOM_Philips.m:364` scales by an
  echo difference and adds "You may use also any individual echo time".
- **Dipole kernel:** `dipole_kernel_angulated(N, voxel_size, B0_dir)`, as `script_invivo.m:44`.
- **Data weight:** see `recon.m`'s header.
- **GPU:** `isGPU = false`. FANSI defaults to the GPU; both the Runtime and the licensed runs run on the CPU.
- **Output:** χ masked by the input mask.
- **Newton guard** (`newton_guard`, default true): see below.

## The Newton guard (an intentional difference from FANSI)
`WH_nlTV.m` solves its nonlinear data step per voxel with up to 50 Newton iterations whose
derivative, `W·cos(z2 − phase) + mu2`, can approach zero. FANSI does not guard the step, and with
the flat weight (W = 1 = mu2) it can jump far from the solution and then go NaN. QSM-CI's in-silico
head with a PDF local field does this in the first ADMM iteration, and the whole map comes out NaN.
[`wh_nltv_newton_guard.patch`](wh_nltv_newton_guard.patch) adds `params.isNewtonGuard`: when set,
each Newton iterate is clamped to `[(rhs − W)/mu2, (rhs + W)/mu2]`, the interval that always holds
the minimiser (its gradient is `W·sin(z2 − phase) + mu2·z2 − rhs`), so the step still converges
to the same solution. An iterate inside the interval is untouched. Even where FANSI's step converges
it sometimes overshoots on the way, so the guard moves maps that never went NaN by about 1e-6 ppm
(NRMSE 0.0001% on the fidelity cases, [`fidelity/REPORT.md`](fidelity/REPORT.md)).
`recon.m` turns it on by default; `newton_guard: false` in `config.json` runs FANSI's step
verbatim. QSM.rs's port has the same guard (QSM.rs#461).

Every other default is `WH_nlTV.m`'s own; `algorithm.yml` lists them.
