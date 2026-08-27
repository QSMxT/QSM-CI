# QSMART (original MATLAB toolbox)

The authors' original **QSMART v1.0** toolbox (Yaghmaie et al., *NeuroImage* 2021;
[wtsyeda/QSMART](https://github.com/wtsyeda/QSMART)), packaged as a **full-pipeline
(`end-to-end`)** QSM-CI submission: phase + magnitude + mask in, susceptibility map out. The
QSM.rs reimplementation of QSMART lives at `../qsmart-qsmrs` (a `bfr+dipole` span); this
submission runs the authors' MATLAB code itself, entering at the earliest point the QSM-CI
contract allows so that the original unwrapping, echo fitting and reliability masking are used.

- **Stage:** `end-to-end` (phase → chimap, ppm)
- **Pipeline (as in `QSMART.m`):** `vasculature_mask` (N4 → bottom-hat → Frangi → Otsu) →
  `unwrap_phase` (Laplacian) → `echofit` (magnitude-weighted LS fit; yields the native **R_0**
  reliability mask) → `QSMART_SDF` stage 1 → `QSM_iLSQR` → `QSMART_SDF` stage 2 (vasculature-
  aware) → `QSM_iLSQR` → `adjust_offset` (dipole-model offset between the two stages).
- **Reference:** Yaghmaie et al., *NeuroImage* 2021 ·
  doi:[10.1016/j.neuroimage.2020.117701](https://doi.org/10.1016/j.neuroimage.2020.117701)

## Deviations from the original `QSMART.m` (packaging only — the science is untouched)

| Original step | Here | Why |
|---|---|---|
| `readComplexDicoms` + `coil_comb` | skipped | QSM-CI inputs are already coil-combined 4-D NIfTIs (phase in radians) |
| `brainmask.m` (N4 + FSL BET) | skipped | the contract `/input/mask.nii.gz` is used, for comparability across submissions |
| `module load ants; N4BiasFieldCorrection` inside `vasculature_mask` | ANTs **N4 baked into the container image** (see `Dockerfile`), invoked directly | the original assumed an HPC module system. If N4 is missing (plain-MATLAB local run) the bias correction is **skipped with a warning** — acceptable on simulated bias-free data; keep N4 in the image for in-vivo faithfulness |
| `mex eig3volume.c` at run time | mex compiled at **build** time | a deployed MATLAB Runtime cannot compile mex |
| `QSM_iLSQR` from the MATLAB path | STI Suite v3 `Core_Functions_P` bundled at build time | QSMART's inversion is STI Suite's `QSM_iLSQR` (Wei Li / Chunlei Liu) — it is not part of the QSMART repo |
| `make_nii`/`save_nii` final output | output written through the input mask's **untouched header** | the bundled NIfTI `make_nii` loses the affine |
| — | odd matrix dims zero-padded to even (and cropped back) | `adjust_offset`'s `-N/2:N/2-1` k-grid and STI's `calcD2Matrix` assume even dims |
| `calculate_curvature`'s `max(abs(GC(GC<0)))` scale | guarded when `GC<0` is empty (build-time patch, see `BUILD.md`) | simulated phantom masks can have no concave surface points → `max([])` = `[]` → hard error; the guard is a no-op whenever negatives exist |
| stray `keyboard` in `FrangiFilter3D.m` | commented out (build-time patch) | a leftover debug statement; fatal ("Debugging is not supported") in deployed MCR mode |

Parameters are the `Demo_QSMART.m` defaults for a human scan (field strength, TEs, voxel size and
B0 direction come from `params.json`; `gyro = 2.675e8`, Laplacian unwrapping). The demo's
`mag_threshold`/`sph_radius1` only feed the skipped BET brain-masking step and are therefore not
exposed. See `BUILD.md` for the compile + image bake, and `algorithm.yml` for the tunables
(Frangi scale range/ratio/C, bottom-hat radius, R_0 fit threshold).

## Licensing of vendored code

Third-party code is fetched at **build time** and never committed (repo convention): the QSMART
toolbox (**no license file; author toolbox distribution**), STI Suite (its own license), the
Jimmy Shen NIfTI toolbox, the Frangi filter + curvatures File Exchange packages (BSD license
files retained), and Hongfu Sun's `lapunwrap.m` (MIT). Only QSM-CI-authored files are committed
(`recon.m`, `vasculature_mask_qsmci.m`, `shims/`, `run.sh`).
