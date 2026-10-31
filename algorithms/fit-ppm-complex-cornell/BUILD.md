# Building fit-ppm-complex-cornell (compiled MATLAB → MATLAB Runtime)

Compile `recon.m` with **licensed MATLAB R2023b + MATLAB Compiler** and bake it onto the R2023b
MATLAB Runtime, as `../pdf-cornell/BUILD.md`. The method is MEDI's field map, as the Cornell
**MEDI toolbox 2024.11.26**'s pipeline script makes it for a unipolar readout (`README.m:80-95`):
`Fit_ppm_complex` (the complex fit QSM.rs ports as `fit_ppm_complex`, `src/utils/multi_echo.rs`)
followed by `unwrapPhase`'s region growing (`mexUnwrap`, Tian Liu; not ported to QSM.rs).

Stage: `field-mapping`. It consumes `phase` (radians, echoes on the 4th axis), `magnitude` and
`params` and writes `totalfield` (ppm) over the whole field of view; neither step takes a mask.

## 1. Fetch build-time deps (not committed)
```bash
cd algorithms/fit-ppm-complex-cornell
cp -r /path/to/NIfTI_20140122 nifti
mkdir -p medi && cp /path/to/MEDI_toolbox-2024.11.26/functions/{Fit_ppm_complex.m,unwrapPhase.m,arlo.m,mexUnwrap.c} medi/
```
`mexUnwrap` is compiled from the shipped `mexUnwrap.c`, as `lbv-cornell` compiles `mexMGv6` (whose
shipped binary predates its source). [`fidelity/config.sh`](fidelity/config.sh) (`fid_assemble`) is the same recipe as a script.

## 2. Compile
```bash
matlab -batch "cd medi; mex mexUnwrap.c"
matlab -batch "addpath('nifti'); addpath('medi'); mcc('-m','recon.m','-a','medi/mexUnwrap.mexa64','-o','recon','-d','.')"
```
Check that `unresolvedSymbols.txt` and `mccExcludedFiles.log` list nothing
(`submit.sh fit-ppm-complex-cornell build`).

## 3. Bake the image and push
```bash
podman build -t ghcr.io/astewartau/qsm-ci/matlab-medi:fitppm-v1 .
podman push  ghcr.io/astewartau/qsm-ci/matlab-medi:fitppm-v1
```
The image is a tag of the public `matlab-medi` package. Pin `image:` by the pushed digest and rerun
the fidelity check. Never overwrite a tag.

## What recon.m does
- **`iField = mag·exp(−i·phase)`**, as MEDI's Siemens and Philips readers build it
  (`Read_Siemens_DICOM.m:178`, `Read_DICOM.m:319`). `Fit_ppm_complex` conjugates it, so a phase
  that grows with TE gives a positive field.
- **`[iFreq_raw, N_std] = Fit_ppm_complex(iField)`** with its defaults (`reltol` 1e-4, `max_iter`
  30). It fits one frequency per echo spacing, so it needs evenly spaced echoes; `recon.m` stops on
  uneven spacing (`README.m` switches to `Fit_ppm_complex_TE` there).
- **`iFreq = unwrapPhase(iMag, iFreq_raw, matrix_size)`**, `iMag = sqrt(sum(|iField|², 4))`.
- **Units:** `totalfield = iFreq / (2π·delta_TE·CF) · 1e6` ppm, `CF` = 42.576 MHz/T · `B0`,
  `delta_TE` = `TE(2) − TE(1)`.

With `QSMCI_INTERMEDIATES` set it also writes ARLO's R2* (`arlo(TE, abs(iField))`, `README.m:133`),
the next step of MEDI's pipeline, so the fidelity check covers ARLO too; QSM-CI has no R2* stage.
