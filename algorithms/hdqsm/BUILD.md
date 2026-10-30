# Building hdqsm (compiled MATLAB → MATLAB Runtime)

Compile `recon.m` with **licensed MATLAB R2023b + MATLAB Compiler** and bake it onto the R2023b
MATLAB Runtime. R2023b because it is the licensed MATLAB the fidelity check runs on
([`../../fidelity/matlab/`](../../fidelity/matlab/README.md)), so the container and the reference
runs share one release. Bundled NIfTI toolbox and OS gzip (no JVM), plus the authors' `HDQSM.m`
(**github.com/mglambert/HD-QSM at c456a94**, its latest commit; QSM.rs's port, `hdqsm-qsmrs`, cites
the repository without a commit) and FANSI's `dipole_kernel_angulated.m` (FANSI-toolbox 93044a3).

Stage: `dipole`. It consumes `localfield` (ppm), `magnitude` (the echoes), `mask` and `params`, runs
`HDQSM.m` and writes `chimap` (ppm).

## 1. Fetch build-time deps (not committed)
```bash
git clone https://github.com/mglambert/HD-QSM.git /tmp/hdqsm && git -C /tmp/hdqsm checkout c456a94
git clone https://gitlab.com/cmilovic/FANSI-toolbox.git /tmp/fansi && git -C /tmp/fansi checkout 93044a3
cd algorithms/hdqsm
cp -r /path/to/NIfTI_20140122 nifti
mkdir -p hdqsm && cp /tmp/hdqsm/HDQSM.m /tmp/fansi/dipole_kernel_angulated.m hdqsm/
```
[`fidelity/config.sh`](fidelity/config.sh) (`fid_assemble`) is the same recipe as a script.

## 2. Compile
```bash
matlab -batch "addpath('nifti'); addpath('hdqsm'); mcc('-m','recon.m','-o','recon','-d','.')"
```
Check that `unresolvedSymbols.txt` and `mccExcludedFiles.log` list nothing (`submit.sh hdqsm build`).

## 3. Bake the image and push
```bash
podman build -t ghcr.io/astewartau/qsm-ci/hd-qsm:v2 .   # needs ./recon from §2
podman push  ghcr.io/astewartau/qsm-ci/hd-qsm:v2
```
The package is public (its `v1` was QSM-CI's earlier, unchecked build). Pin `image:` in
`algorithm.yml` by the pushed digest and rerun the fidelity check
([`fidelity/REPORT.md`](fidelity/REPORT.md)). Never overwrite a tag.

## Inputs and defaults
As `HDQSM.m`'s usage example (L27-34):
- **`input`:** the masked local field in ppm (the example's `phase_use/phase_scale`).
- **`weight`:** `mask .* mag_use/max(mag_use)`, with `mag_use` the paper's echo combination
  `Σ TEᵢ·magᵢ² / Σ TEᵢ·magᵢ` (Eq. 2).
- **`kernel`:** HD-QSM ships none; it is FANSI's `dipole_kernel_angulated(N, voxel_size, B0_dir)`,
  since `HDQSM.m` is "based on" FANSI.
- **`alphaL2`, `mu1L2`:** `HDQSM.m` has no default. The example uses `10^-4.785` and `10·alphaL2`;
  `recon.m` uses QSM.rs's `HdQsmParams` (3e-5, `100·alphaL2`), because with a ratio of 10 the ADMM
  diverges on in vivo scans at the `alphaL2` that suits them, in `HDQSM.m` as in the port.
- Everything else is `HDQSM.m`'s own: 20 L1 and 80 L2 iterations, `tol_update` 1e-2 (the code; its
  header says 1.0), `mu1L1 = sqrt(mu1L2)`, `alphaL1 = sqrt(alphaL2)`, `mu2` 1.

χ is masked by the input mask.
