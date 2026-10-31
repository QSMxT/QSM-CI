# Building lsqr (compiled MATLAB → MATLAB Runtime)

Compile `recon.m` with **licensed MATLAB R2023b + MATLAB Compiler** and bake it onto the R2023b
MATLAB Runtime. R2023b because it is the licensed MATLAB the fidelity check runs on
([`../../fidelity/matlab/`](../../fidelity/matlab/README.md)), so the container and the reference
runs share one release. Bundled NIfTI toolbox and OS gzip (no JVM), plus the authors' **qsm_heidi
at commit 4592631** (gitlab.com/R01NS114227/qsm_heidi), the commit QSM.rs's port (`lsqr-qsmrs`)
cites.

Stage: `dipole`. It consumes `localfield` (ppm), `magnitude` (the echoes), `mask` and `params`, runs
the minimally regularised LSQR inversion as `inversion_lsqr.m` does, and writes `chimap` (ppm).

## 1. Fetch build-time deps (not committed)
```bash
git clone https://gitlab.com/R01NS114227/qsm_heidi.git /tmp/qsm_heidi && git -C /tmp/qsm_heidi checkout 4592631
cd algorithms/lsqr
cp -r /path/to/NIfTI_20140122 nifti
mkdir -p lsqr && cp /tmp/qsm_heidi/lsqr/*.m lsqr/
cp /tmp/qsm_heidi/LICENSE LICENSE.qsm_heidi     # the license asks for its notice in every copy
```
[`fidelity/config.sh`](fidelity/config.sh) (`fid_assemble`) is the same recipe as a script.

## 2. Compile
```bash
matlab -batch "addpath('nifti'); addpath('lsqr'); mcc('-m','recon.m','-o','recon','-d','.')"
```
`lsqr/` goes first on the path, as `inversion_lsqr.slurm` runs MATLAB from that folder. Everything
is plain `.m`, so mcc traces it all. Check that `unresolvedSymbols.txt` and `mccExcludedFiles.log`
list nothing (`submit.sh lsqr build`).

## 3. Bake the image and push
```bash
podman build -t ghcr.io/astewartau/qsm-ci/heidi:lsqr-v2 .   # needs ./recon and ./LICENSE.qsm_heidi
podman push  ghcr.io/astewartau/qsm-ci/heidi:lsqr-v2
```
Make the `heidi` package public (a new package starts private; it holds the `lsqr` and `heidi` images), pin `image:` in `algorithm.yml` by the
pushed digest, and rerun the fidelity check ([`fidelity/REPORT.md`](fidelity/REPORT.md)).

## What recon.m does
`inversion_lsqr.m` reads the pipeline's `.mat` files (mids objects: the SHARP-corrected phase, the
magnitude, and masks from a step not in the repository). `recon.m` gives its computational core,
`computesusceptibility_lsqr`, the same values from QSM-CI's inputs, with every option
`inversion_lsqr.m` sets:
- **Phase:** the local field as the phase in radians at the last echo time,
  `−field·1e-6·γ·B0·TE_last`, γ = 2.67522128e8 rad/s/T (`getconstants.m`). The minus sign is the
  rotating-frame convention `phase2susceptibilityfactor.m` defaults to, which converts back with
  `χ = −x·phase2susceptibilityfactor·1e6`; so χ has the sign of QSM-CI's ppm. The last echo time is
  the one `phase2susceptibilityfactor.m` takes (L70-71); LSQR is linear, so it does not change χ.
- **Mask:** QSM-CI's mask, for `mask_tissue .* mask_phase .* mask`.
- **Magnitude:** the root sum of squares of the echo magnitudes (QSMxT's combined magnitude).
- **Grid:** `zealouscrop` to the mask's bounding box and `prepareforconvolution` with the 40-voxel
  anti-aliasing frame, undone at the end.
- **Options:** `tolerance` 1e-5, `maxit` 400, `offsetUseBool` true, `isFourierDomainFormula` false
  (the dipole sampled in the spatial domain), `residualWeighting` 0.2/9.4·B0, no Tikhonov term,
  solving type or dipole filter.
- **Orientation:** the authors take `Options.Rotation` from the DICOM orientation; an axial scan's is
  angle 0, which `recon.m` passes (`angle` 0, `axis` [0 0 1]). It has to be given: with no
  `Rotation` the cores fall back to SEPIA's k-space `DipoleKernel`, not the spatial-domain dipole
  of `generateunitdipoleresponse` that `inversion_*.m` select and QSM.rs ports. `recon.m` stops on
  an oblique `B0_dir`.

χ is left unmasked, as `inversion_lsqr.m` leaves it (0 outside the crop).

## Exiting
`computesusceptibility_lsqr.m` ends with an unconditional `figure; plot(...)` of LSQR's residual history. A
compiled binary does not exit while a figure is open, so `recon.m` ends with `close all force;` once `chimap` is
written (images before `*-v2` hung until the job's time limit). The numbers are unchanged.
