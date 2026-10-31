# lsqr fidelity report

QSMxT/QSM-CI#300: does the `lsqr` container compute what the authors' MATLAB computes? The check is
the shared harness [`fidelity/matlab/`](../../../fidelity/matlab/README.md) with this algorithm's
[`config.sh`](config.sh); rerun it whenever `recon.m`, its dependencies or the image change.

- **Checked:** 2026-10-31, on Slurm compute nodes, 8 CPUs per job.
- **Licensed MATLAB:** 23.2.0.2459199 (R2023b) Update 5, with the real toolboxes.
- **Image checked:** `ghcr.io/astewartau/qsm-ci/heidi@sha256:be334a2c06cd37474175b98950387fc027c40fddf12066d5b4de8d09f6e7e3a4` (`lsqr-v2`).
  - `recon` is compiled with that licensed R2023b against the real toolboxes, with no shims.
  - It runs on the R2023b MATLAB Runtime (23.2.0.3097123 (R2023b) Update 11) under Apptainer.
- **Previous image:** `lsqr-v1` `sha256:b4cab7ed78d98c1a02e0d3c1ae68d2e890fd2fe1c7da358ad90d5091a389c335` wrote the
  same outputs but never exited (below); `lsqr-v2` only adds `close all force;` at the end of `recon.m`.
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

**Cause (likely, not proven):** the container runs the R2023b Runtime at Update 11 and licensed MATLAB is Update 5.
On Bunya, the Runtime's FFTW (`libmwfftw3.so.3.5.8`), BLAS, LAPACK and MKL libraries are byte-identical to the
licensed installation's, but `libmwmathcore.so` differs, and the Runtime's `lsqr.m` is encrypted, so it can't be
compared. A rounding difference early in LSQR's Krylov recurrence is enough to move its stopping iteration. The
residual shows only on the in-silico grid (164×205×205, two odd dimensions); RESHARP shows the same in-silico-only
pattern. A Runtime image at Update 5 (`containers.mathworks.com/matlab-runtime:r2023b-update-5`) would test this.

**Exit hang (fixed in `lsqr-v2`):** `computesusceptibility_lsqr.m` ends with an unconditional `figure; plot(...)` of
the residual history. Licensed MATLAB `-batch` exits anyway, but a compiled binary does not exit while a figure is
open: `lsqr-v1` wrote every output in about 3 minutes and then waited until the job's 2.5 h limit (jobs 31154776,
31154780). `recon.m` now ends with `close all force;`, after `chimap` is written; the numbers are unchanged.

**Where the functions resolved** (`intermediates.json`): `computesusceptibility_lsqr`, `generateunitdipoleresponse`,
`zealouscrop`, `prepareforconvolution`, `phase2susceptibilityfactor` and `getconstants` resolve to the bundled
`deps/lsqr` in the container's extracted archive and in licensed MATLAB; `lsqr` to the Runtime's
`toolbox/matlab/sparfun` in the container and to the licensed installation's in MATLAB. The build's
`unresolvedSymbols.txt` and `mccExcludedFiles.log` list nothing, and `requiredMCRProducts.txt` lists
35000, 35002, 35003, 35010, 35117, 35166, 35180 (the graphics products come from the residual plot).

## Slurm jobs

| What | Job ids |
|---|---|
| Compile | 31198620 (`lsqr-v2`; 31130156: `lsqr-v1`) |
| Setup | 31198966 |
| sim: container, real, real2, compare | 31198967, 31198968, 31198969, 31198970 |
| invivo: container, real, real2, compare | 31198971, 31198972, 31198973, 31198974 |
| `lsqr-v1` (container timed out; compared afterwards on its outputs) | 31154775–31154783, compares 31198603, 31198604 |
