# lsqr fidelity report

QSMxT/QSM-CI#300: does the `lsqr` container compute what the authors' MATLAB computes? The check is
the shared harness [`fidelity/matlab/`](../../../fidelity/matlab/README.md) with this algorithm's
[`config.sh`](config.sh); rerun it whenever `recon.m`, its dependencies or the image change.

- **Checked:** 2026-11-01, on Slurm compute nodes, 8 CPUs per job.
- **Licensed MATLAB:** 23.2.0.2459199 (R2023b) Update 5, with the real toolboxes.
- **Image checked:** `ghcr.io/astewartau/qsm-ci/heidi@sha256:a2deee2d35a926871a838509324014dbc482e4ca5c02fc09b1fed348376a8229` (`lsqr-v4`).
  - `recon` is compiled with that licensed R2023b against the real toolboxes, with no shims.
  - It runs on the R2023b MATLAB Runtime (23.2.0.3097123 (R2023b) Update 11) under Apptainer.
- **Previous images:** `lsqr-v1` `sha256:b4cab7ed78d98c1a02e0d3c1ae68d2e890fd2fe1c7da358ad90d5091a389c335` wrote the
  same outputs but never exited; `lsqr-v2` `sha256:be334a2c06cd37474175b98950387fc027c40fddf12066d5b4de8d09f6e7e3a4` added
  `close all force;` (below); `lsqr-v4` also crops the mask with frame value 0, so a mask with no zero border runs
  (below). Each gave the same numbers on both cases. (`lsqr-v3` was `lsqr-v2` on the Update 5 Runtime, below.)
- **Sources:** gitlab.com/R01NS114227/qsm_heidi 4592631 (`lsqr/`: `computesusceptibility_lsqr.m` and the helpers it calls).
- **Cases:**
  - `sim`: QSM-CI's in-silico head (QSM Challenge 2.0 simulation: 7 T, 4 echoes, 1 mm, 164×205×205), its ground-truth local field and its magnitude.
  - `invivo`: one EMTP travelling-head acquisition (`s005001-cbic-prisma-bridge-run1`: 3 T, 5 echoes, 1 mm, 184×256×128), with the local field and eroded mask derived once with QSMxT v10.0.0 (ROMEO, V-SHARP; `fidelity/matlab/make_cases.sh`) and its magnitude.

## Result: identical in vivo; a residual in silico

| Output | sim: container vs real | invivo: container vs real | real2 vs real (sim, invivo) |
|---|---|---|---|
| `chimap.nii.gz` | NRMSE 0.059 %, max \|Δ\| 0.0023 ppm | identical | identical |
| `intermediates/chimap_f64.nii.gz` | NRMSE 0.059 %, max \|Δ\| 0.0023 ppm | identical | identical |
| `intermediates/lsqr_residual.nii.gz` | NRMSE 0.135 %, max \|Δ\| 0.032 | identical | identical |
| `intermediates/phase_input.nii.gz` | identical | identical | identical |

NRMSE and max |Δ| are 0 and no voxel differs wherever a cell says identical.
The container and the licensed runs all used 8 threads (recorded in `intermediates.json`), on the same node.

In silico the input phase is identical, licensed MATLAB is bit-repeatable (real2 = real), and the container is
repeatable too (`lsqr-v1` and `lsqr-v2` give the same numbers), but the solver stops at a different iteration:
licensed MATLAB converges after 204 iterations (normalised residual 3.281e-4), the container after 198 (3.548e-4).
In vivo both take 355 iterations to the same residual (5.3223e-4) and every output is identical.

**Cause: the container's operating system, not MATLAB.** Probed on the in-silico case (all at 8 threads):
- **Not the Runtime update:** `lsqr-v3`, the same `recon` on the Update 5 Runtime
  (`containers.mathworks.com/matlab-runtime:r2023b-update-5@sha256:4071c142…`, the licensed build 23.2.0.2459199),
  gives the same numbers as `lsqr-v2` on Update 11 (198 iterations; jobs 31200790–31200794). `lsqr-v2` stays.
- **Not compilation:** the compiled `recon` run on the host (RHEL 9, glibc 2.34) against the licensed installation's
  libraries reproduces licensed MATLAB bit for bit (204 iterations; job 31201080).
- **The OS userland:** the licensed installation's libraries run inside the image's Ubuntu 22.04 userland (glibc 2.35)
  reproduce the container bit for bit (198 iterations; job 31201136).

So MATLAB itself is the same; what differs is a system library under it, most likely glibc's libm (MATLAB's
FFTW, BLAS, LAPACK and MKL are its own and byte-identical). A rounding difference early in LSQR's Krylov recurrence
moves its stopping iteration. The residual shows only on the in-silico grid (164×205×205, two odd dimensions).
MathWorks' Runtime images are all Ubuntu-based, so a different base image can't remove it.

**Exit hang (fixed in `lsqr-v2`):** `computesusceptibility_lsqr.m` ends with an unconditional `figure; plot(...)` of
the residual history. Licensed MATLAB `-batch` exits anyway, but a compiled binary does not exit while a figure is
open: `lsqr-v1` wrote every output in about 3 minutes and then waited until the job's 2.5 h limit (jobs 31154776,
31154780). `recon.m` now ends with `close all force;`, after `chimap` is written; the numbers are unchanged.

**Mask with no zero border (fixed in `lsqr-v4`):** `inversion_lsqr.m` crops with `zealouscrop(mask)`, which takes
the value to crop from the mask's edge rows. QSM-CI's smoke test gives a 32³ box inside the brain, all ones, which
that call crops to 1×1, so `computesusceptibility_lsqr` stopped with "Index exceeds the number of array elements"
(licensed MATLAB too). `recon.m` now passes frame value 0, as the authors' `prepareforconvolution.m` crops a mask, so
only all-0 slices are removed. On both fidelity cases the crop is unchanged (checked on their masks), and the smoke
box now runs (44 s in licensed MATLAB; BUILD.md).

**Where the functions resolved** (`intermediates.json`): `computesusceptibility_lsqr`, `generateunitdipoleresponse`,
`zealouscrop`, `prepareforconvolution`, `phase2susceptibilityfactor` and `getconstants` resolve to the bundled
`deps/lsqr` in the container's extracted archive and in licensed MATLAB; `lsqr` to the Runtime's
`toolbox/matlab/sparfun` in the container and to the licensed installation's in MATLAB. The build's
`unresolvedSymbols.txt` and `mccExcludedFiles.log` list nothing, and `requiredMCRProducts.txt` lists
35000, 35002, 35003, 35010, 35117, 35166, 35180 (the graphics products come from the residual plot).

## Slurm jobs

| What | Job ids |
|---|---|
| Compile | 31205536 (`lsqr-v4`; 31198620: `lsqr-v2`; 31130156: `lsqr-v1`) |
| Setup | 31205555 |
| sim: container, real, real2, compare | 31205556, 31205557, 31205558, 31205559 |
| invivo: container, real, real2, compare | 31205560, 31205561, 31205562, 31205563 |
| `lsqr-v2` (setup; sim; invivo) | 31198966; 31198967–31198970; 31198971–31198974 |
| `lsqr-v1` (container timed out; compared afterwards on its outputs) | 31154775–31154783, compares 31198603, 31198604 |
| `lsqr-v3` on the Update 5 Runtime (setup, sim and invivo container + compare) | 31200790–31200794 |
| Probes: compiled `recon` on the host; licensed libraries in the image's userland | 31201080; 31201136 |
| Smoke box (licensed MATLAB): reproduction; fix check, with the crop on both fidelity masks | 31205390; 31205412 |
