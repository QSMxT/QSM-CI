# Building heidi (compiled MATLAB → MATLAB Runtime)

Compile `recon.m` with **licensed MATLAB R2023b + MATLAB Compiler** and bake it onto the R2023b
MATLAB Runtime. R2023b because it is the licensed MATLAB the fidelity check runs on
([`../../fidelity/matlab/`](../../fidelity/matlab/README.md)), so the container and the reference
runs share one release. Bundled NIfTI toolbox and OS gzip (no JVM), plus the authors' **qsm_heidi
at commit 4592631** (gitlab.com/R01NS114227/qsm_heidi), the commit QSM.rs's port (`heidi-qsmrs`)
cites.

Stage: `dipole`. It consumes `localfield` (ppm), `magnitude` (the echoes), `mask` and `params`, runs
LSQR and then HEIDI as the repository's pipeline does (`makefile`, `def.sh`: `inversion_lsqr.m`, then
`inversion_heidi.m` on its result), and writes `chimap` (ppm).

## 1. Fetch build-time deps (not committed)
```bash
git clone https://gitlab.com/R01NS114227/qsm_heidi.git /tmp/qsm_heidi && git -C /tmp/qsm_heidi checkout 4592631
cd algorithms/lsqr
cp -r /path/to/NIfTI_20140122 nifti
mkdir -p lsqr heidi itk && cp /tmp/qsm_heidi/lsqr/*.m lsqr/ && cp /tmp/qsm_heidi/heidi/*.m heidi/
cp /tmp/qsm_heidi/LICENSE LICENSE.qsm_heidi     # the license asks for its notice in every copy
# HEIDI denoises its gradient mask with the ITK 3.20 executable the repository ships:
cp /tmp/qsm_heidi/heidi/GradientAnisotropicDiffusionImageFilter /tmp/qsm_heidi/heidi/lib*.so.3.20 itk/
# reppath.m finds that executable next to itself (which('reppath.m')), which in a compiled binary is
# the extracted archive. One line lets the image name the folder (QSMCI_HEIDI_ITK); unset, nothing changes:
perl -0pi -e "s/(function Path = reppath\(\)\r?\n)/\$1    if ~isempty(getenv('QSMCI_HEIDI_ITK')), Path = [getenv('QSMCI_HEIDI_ITK') '\/']; return; end  % QSM-CI, see BUILD.md\n/" heidi/reppath.m
```
[`fidelity/config.sh`](fidelity/config.sh) (`fid_assemble`) is the same recipe as a script.

## 2. Compile
```bash
matlab -batch "addpath('nifti'); addpath('lsqr'); addpath('heidi'); mcc('-m','recon.m','-o','recon','-d','.')"
```
`heidi/` goes first on the path, as `inversion_heidi.slurm` runs MATLAB from that folder; `lsqr/`
holds the seed's core. The two folders share every other file but `load_nii_raw.m` and `write_nii.m`,
which HEIDI's denoising uses, so `heidi/`'s win. Everything
is plain `.m`, so mcc traces it all. Check that `unresolvedSymbols.txt` and `mccExcludedFiles.log`
list nothing (`submit.sh heidi build`).

## 3. Bake the image and push
```bash
podman build -t ghcr.io/astewartau/qsm-ci/heidi:heidi-v4 .   # needs ./recon, ./itk and ./LICENSE.qsm_heidi
podman push  ghcr.io/astewartau/qsm-ci/heidi:heidi-v4
```
Make the `heidi` package public (a new package starts private; it holds the `lsqr` and `heidi` images), pin `image:` in `algorithm.yml` by the
pushed digest, and rerun the fidelity check ([`fidelity/REPORT.md`](fidelity/REPORT.md)).

## What recon.m does
`inversion_lsqr.m` and `inversion_heidi.m` read the pipeline's `.mat` files (mids objects: the SHARP-corrected phase, the
magnitude, and masks from a step not in the repository). `recon.m` gives its computational core,
`computesusceptibility_lsqr` and then `computesusceptibility_heidi`, the same values from QSM-CI's
inputs, with every option `inversion_lsqr.m` and `inversion_heidi.m` set:
- **Phase:** the local field as the phase in radians at the last echo time,
  `−field·1e-6·γ·B0·TE_last`, γ = 2.67522128e8 rad/s/T (`getconstants.m`). The minus sign is the
  rotating-frame convention `phase2susceptibilityfactor.m` defaults to, which converts back with
  `χ = −x·phase2susceptibilityfactor·1e6`; so χ has the sign of QSM-CI's ppm. The last echo time is
  the one `phase2susceptibilityfactor.m` takes (L70-71), and HEIDI also normalises its gradient and
Laplacian thresholds by it.
- **Mask:** QSM-CI's mask, for `mask_tissue .* mask_phase .* mask`.
- **Magnitude:** the root sum of squares of the echo magnitudes (QSMxT's combined magnitude).
- **Grid:** `zealouscrop` to the mask's bounding box (frame value 0; see "Cropping a mask with no zero border" below) and `prepareforconvolution` with the 40-voxel
  anti-aliasing frame, undone at the end.
- **HEIDI's seed** is LSQR's result before the unit conversion (`susceptibilityRaw`), on the same
  grid, as `inversion_heidi.m` loads it from `inversion_lsqr.mat`.
- **HEIDI's options:** `useHEIDI` true, `PostProcCone.threshold` 0.1, `PostProcCone.tol` and
  `tolEnergy` eps (so NESTA runs all 8 × 500 iterations), `isFourierDomainFormula` false; the rest
  are `computesusceptibility_heidi.m`'s defaults, including the gradient-mask denoising with ITK's
  gradient anisotropic diffusion (5 iterations, time step 0.05, conductance 1).
- **LSQR's options:** `tolerance` 1e-5, `maxit` 400, `offsetUseBool` true, `isFourierDomainFormula` false
  (the dipole sampled in the spatial domain), `residualWeighting` 0.2/9.4·B0, no Tikhonov term,
  solving type or dipole filter.
- **Orientation:** the authors take `Options.Rotation` from the DICOM orientation; an axial scan's is
  angle 0, which `recon.m` passes (`angle` 0, `axis` [0 0 1]). It has to be given: with no
  `Rotation` the cores fall back to SEPIA's k-space `DipoleKernel`, not the spatial-domain dipole
  of `generateunitdipoleresponse` that `inversion_*.m` select and QSM.rs ports. `recon.m` stops on
  an oblique `B0_dir`.

χ is left unmasked, as `inversion_heidi.m` leaves it (0 outside the crop).

## Deviation from the authors' code
`reppath.m` gets one line (above) so the compiled binary finds the ITK executable in the image
(`/opt/heidi-itk`). In licensed MATLAB the variable is unset and `reppath` is the original; both runs
use the same executable and libraries, copied from the repository.

## Exiting
`computesusceptibility_lsqr.m` ends with an unconditional `figure; plot(...)` of LSQR's residual history. A
compiled binary does not exit while a figure is open, so `recon.m` ends with `close all force;` once `chimap` is
written (images before `*-v2` hung until the job's time limit). The numbers are unchanged.

## Cropping a mask with no zero border
`inversion_*.m` call `zealouscrop(mask)` with no frame value, so `zealouscrop` takes the value to crop from
the mask's edge rows. That works for a full-FOV brain mask, which has zero background at the edge. A mask
with no zero border, such as QSM-CI's smoke test (a 32³ box inside the brain, all ones), has only uniform
all-1 slices: the call crops it to 1×1, and `computesusceptibility_lsqr` stops with "Index exceeds the
number of array elements" (licensed MATLAB does the same). `recon.m` passes frame value 0, as the
authors' `prepareforconvolution.m` crops a mask (`zealouscrop(mask, [], 0)`), so only all-0 slices are
removed. For any mask with zero background at the edge the crop is the same (checked on both fidelity
cases' masks); a mask with none is not cropped.
