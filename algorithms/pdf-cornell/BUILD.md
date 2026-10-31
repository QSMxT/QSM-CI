# Building pdf-cornell (compiled MATLAB → MATLAB Runtime)

Compile `recon.m` with **licensed MATLAB R2023b + MATLAB Compiler** and bake it onto the R2023b
MATLAB Runtime. R2023b because it is the licensed MATLAB the fidelity check runs on
([`../../fidelity/matlab/`](../../fidelity/matlab/README.md)), so the container and the reference
runs share one release. Same patterns as `../medi-cornell/BUILD.md` (bundled NIfTI toolbox, OS gzip,
no JVM, no toolbox shims), with the Cornell **MEDI toolbox 2024.11.26**, the release QSM.rs's PDF
port (`src/bgremove/pdf.rs`) follows.

Stage: `bfr`. It consumes `totalfield` (ppm), `magnitude` (the echoes), `mask` and `params`, runs
`PDF.m` and writes `localfield` (ppm).

## 1. Fetch build-time deps (not committed)
```bash
cd algorithms/pdf-cornell
cp -r /path/to/NIfTI_20140122 nifti                     # Jimmy Shen NIfTI toolbox
mkdir -p medi && cp /path/to/MEDI_toolbox-2024.11.26/functions/{PDF,Fit_ppm_complex,dipole_kernel,dipole_term,cgsolve}.m medi/
```
These are all the MEDI functions `recon.m` reaches. [`fidelity/config.sh`](fidelity/config.sh)
(`fid_assemble`) is the same recipe as a script.

## 2. Compile
```bash
matlab -batch "addpath('nifti'); addpath('medi'); mcc('-m','recon.m','-o','recon','-d','.')"
```
Everything is plain `.m`, so mcc traces it all; `PDF.m` calls the Image Processing Toolbox's
`padarray`, compiled from the licensed toolbox. Check that `unresolvedSymbols.txt` and
`mccExcludedFiles.log` list nothing. The harness does this compile as a Slurm job
(`submit.sh pdf-cornell build`; log in `reports/build.txt`).

## 3. Bake the image and push
```bash
podman build -t ghcr.io/astewartau/qsm-ci/matlab-medi:pdf-v1 .   # needs ./recon from §2
podman push  ghcr.io/astewartau/qsm-ci/matlab-medi:pdf-v1
```
The image is a tag of the public `matlab-medi` package, which also holds `medi-cornell`'s. Pin
`image:` in `algorithm.yml` by the pushed digest and rerun the fidelity check
([`fidelity/REPORT.md`](fidelity/REPORT.md)). Never overwrite a tag.

## Defaults: PDF.m's own
`tol` 0.1, `n_CG` 30, `'imagespace'`, `n_pad` 40: what `PDF.m` does when the arguments are not
passed, which is also what MEDI's pipeline script runs (`README.m:124`,
`PDF(iFreq, N_std, Mask, matrix_size, voxel_size, B0_dir)`). QSM.rs's `PdfParams::n_cg` defaults to
300, so a parity pair sets one side to match the other.

## Inputs and units
`recon.m` fills PDF's arguments as `README.m` does, from QSM-CI's inputs:
- **`iFreq`** is the total field in MEDI's units, radians accumulated over the echo spacing:
  `field·1e-6·2π·CF·delta_TE`, with `CF` = 42.576 MHz/T · `B0` and `delta_TE` = `TE(2) − TE(1)`
  (`TE` for one echo), as `Read_DICOM`. The local field is converted back to ppm.
- **`N_std`** from `Fit_ppm_complex` on the echo magnitudes. `README.m` takes it from the complex
  echoes; its noise estimate (`dp1`) depends only on their magnitudes, so it is the same `N_std`.
  PDF's weights are `1/N_std`, and its CG tolerance scales with `N_std` relative to the field, so
  both are in MEDI's units.
- **`Mask`** is QSM-CI's mask, where `README.m` runs BET.
