# Building fansi-nltgv (compiled MATLAB → MATLAB Runtime)

Compile `recon.m` with **licensed MATLAB R2023b + MATLAB Compiler** and bake it onto the R2023b
MATLAB Runtime. R2023b because it is the licensed MATLAB the fidelity check runs on
([`../../fidelity/matlab/`](../../fidelity/matlab/README.md)), so the container and the reference
runs share one release. Bundled NIfTI toolbox and OS gzip (no JVM), plus the authors' **FANSI
toolbox at commit 93044a3** (gitlab.com/cmilovic/FANSI-toolbox), the commit QSM.rs's port
(`fansi-nltgv-qsmrs`) cites.

Stage: `dipole`. It consumes `localfield` (ppm), `mask`, `params`, and `magnitude` (the echoes, for the data weight), runs `nlTGV.m` and writes `chimap` (ppm).

## 1. Fetch build-time deps (not committed)
```bash
git clone https://gitlab.com/cmilovic/FANSI-toolbox.git /tmp/fansi && git -C /tmp/fansi checkout 93044a3
cd algorithms/fansi-nltgv
cp -r /path/to/NIfTI_20140122 nifti
mkdir -p fansi && for f in nlTGV.m dipole_kernel_angulated.m; do cp /tmp/fansi/$f fansi/; done
```
These are every FANSI file `recon.m` reaches. [`fidelity/config.sh`](fidelity/config.sh)
(`fid_assemble`) is the same recipe as a script.

## 2. Compile
```bash
matlab -batch "addpath('nifti'); addpath('fansi'); mcc('-m','recon.m','-o','recon','-d','.')"
```
Everything is plain `.m`, so mcc traces it all. Check that `unresolvedSymbols.txt` and
`mccExcludedFiles.log` list nothing. The harness does this compile as a Slurm job
(`submit.sh fansi-nltgv build`; log in `reports/build.txt`).

## 3. Bake the image and push
```bash
podman build -t ghcr.io/astewartau/qsm-ci/fansi:nltgv-v2 .   # needs ./recon from §2
podman push  ghcr.io/astewartau/qsm-ci/fansi:nltgv-v2
```
The package is public (its `v1` was QSM-CI's earlier, unchecked FANSI-family build). Pin `image:` in
`algorithm.yml` by the pushed digest and rerun the fidelity check
([`fidelity/REPORT.md`](fidelity/REPORT.md)). Never overwrite a tag.

## Inputs, units and defaults
`recon.m` follows the FANSI toolbox's own example scripts:
- **Units.** FANSI works on the local phase in radians. The field is scaled by FANSI's
  `phs_scale = te·gyro·B0`, `gyro = 2π·42.58` (`script_invivo.m:58-62`), and χ = `out.x/phs_scale`.
  `te` is the echo spacing `TE(2) − TE(1)`, QSM.rs's default for this method; `script_DICOM_Philips.m:364` scales by an
  echo difference and adds "You may use also any individual echo time".
- **Dipole kernel:** `dipole_kernel_angulated(N, voxel_size, B0_dir)`, as `script_invivo.m:44`.
- **Data weight:** see `recon.m`'s header.
- **GPU:** `isGPU = false`. FANSI defaults to the GPU; both the Runtime and the licensed runs run on the CPU.
- **Output:** χ masked by the input mask.

Every other default is `nlTGV.m`'s own; `algorithm.yml` lists them.
