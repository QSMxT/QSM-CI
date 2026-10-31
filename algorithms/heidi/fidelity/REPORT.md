# heidi fidelity report

QSMxT/QSM-CI#300: does the `heidi` container compute what the authors' MATLAB computes? The check is
the shared harness [`fidelity/matlab/`](../../../fidelity/matlab/README.md) with this algorithm's
[`config.sh`](config.sh); rerun it whenever `recon.m`, its dependencies or the image change.

- **Checked:** 2026-10-31, on Slurm compute nodes, 8 CPUs per job.
- **Licensed MATLAB:** 23.2.0.2459199 (R2023b) Update 5, with the real toolboxes.
- **Image checked:** `ghcr.io/astewartau/qsm-ci/heidi@sha256:5eb9366203b482e4a0dfa372b57dc6521db21676e22905351c132b18b2619104` (`heidi-v2`).
  - `recon` is compiled with that licensed R2023b against the real toolboxes, with no shims.
  - It runs on the R2023b MATLAB Runtime (23.2.0.3097123 (R2023b) Update 11) under Apptainer.
- **Previous image:** `heidi-v1` `sha256:bda981d9481fbb15c21e2233d61b1892ccb3471b15bad7bb3e6ebe89fdf3ed1d` wrote the
  same outputs but never exited (below); `heidi-v2` only adds `close all force;` at the end of `recon.m`.
- **Sources:** gitlab.com/R01NS114227/qsm_heidi 4592631 (`heidi/` and `lsqr/`: LSQR's seed, then
  `computesusceptibility_heidi.m`, with the ITK 3.20 `GradientAnisotropicDiffusionImageFilter` the repository ships).
- **Cases:**
  - `sim`: QSM-CI's in-silico head (QSM Challenge 2.0 simulation: 7 T, 4 echoes, 1 mm, 164×205×205), its ground-truth local field and its magnitude.
  - `invivo`: one EMTP travelling-head acquisition (`s005001-cbic-prisma-bridge-run1`: 3 T, 5 echoes, 1 mm, 184×256×128), with the local field and eroded mask derived once with QSMxT v10.0.0 (ROMEO, V-SHARP; `fidelity/matlab/make_cases.sh`) and its magnitude.

## Result: identical in vivo; a residual in silico, inherited from LSQR's seed

| Output | sim: container vs real | invivo: container vs real | real2 vs real (sim, invivo) |
|---|---|---|---|
| `chimap.nii.gz` | NRMSE 0.073 %, max \|Δ\| 0.0050 ppm | identical | identical |
| `intermediates/chimap_f64.nii.gz` | NRMSE 0.073 %, max \|Δ\| 0.0050 ppm | identical | identical |
| `intermediates/chi_lsqr.nii.gz` (the LSQR seed) | NRMSE 0.059 %, max \|Δ\| 0.0023 ppm | identical | identical |
| `intermediates/phase_input.nii.gz` | identical | identical | identical |

NRMSE and max |Δ| are 0 and no voxel differs wherever a cell says identical.
The container and the licensed runs all used 8 threads (recorded in `intermediates.json`). Licensed MATLAB is
bit-repeatable (real2 = real), and `heidi-v1` and `heidi-v2` give the same numbers.

In silico the seed already differs: it is exactly the `lsqr` entry's residual (LSQR stops after 198 iterations in the
container and 204 in licensed MATLAB; see [`../../lsqr/fidelity/REPORT.md`](../../lsqr/fidelity/REPORT.md)). HEIDI
starts from that seed, so its output differs too; this check can't separate HEIDI's own steps from the seed's
difference in silico. In vivo the seed and everything after it are identical, including the ITK gradient-mask
denoising and NESTA's 8 × 500 iterations.

**Cause (likely, not proven):** the container runs the R2023b Runtime at Update 11 and licensed MATLAB is Update 5.
On Bunya, the Runtime's FFTW (`libmwfftw3.so.3.5.8`), BLAS, LAPACK and MKL libraries are byte-identical to the
licensed installation's, but `libmwmathcore.so` differs, and the Runtime's `lsqr.m` is encrypted, so it can't be
compared. The residual shows only on the in-silico grid (164×205×205, two odd dimensions). A Runtime image at
Update 5 (`containers.mathworks.com/matlab-runtime:r2023b-update-5`) would test this.

**Exit hang (fixed in `heidi-v2`):** LSQR's `computesusceptibility_lsqr.m` ends with an unconditional
`figure; plot(...)`. A compiled binary does not exit while a figure is open: `heidi-v1` wrote every output in about
45 minutes and then waited until the job's 8.5 h limit (jobs 31154794, 31154798). `recon.m` now ends with
`close all force;`, after `chimap` is written; the container now exits after about 50 minutes.

**Deviation:** `reppath.m` gets the one line BUILD.md describes (`reports/deviations.diff`), so the compiled binary
finds the ITK executable at `/opt/heidi-itk`; unset in licensed MATLAB, where `reppath` is the original. Both use the
same executable and libraries, copied from the repository.

**Where the functions resolved** (`intermediates.json`): `computesusceptibility_heidi`, `computesusceptibility_lsqr`,
`Core_Nesterov_fs`, `diffusionimagefilter`, `reppath`, `generateunitdipoleresponse`, `discretegradient`,
`zealouscrop`, `prepareforconvolution`, `phase2susceptibilityfactor`, `write_nii` and `load_nii_raw` resolve to the
bundled `deps/heidi` and `deps/lsqr` in the container's extracted archive and in licensed MATLAB; `lsqr` to the
Runtime's `toolbox/matlab/sparfun` in the container and to the licensed installation's in MATLAB. The build's
`unresolvedSymbols.txt` and `mccExcludedFiles.log` list nothing, and `requiredMCRProducts.txt` lists
35000, 35002, 35003, 35010, 35108, 35117, 35166, 35180, 35380.

## Slurm jobs

| What | Job ids |
|---|---|
| Compile | 31198619 (`heidi-v2`; 31130157: `heidi-v1`) |
| Setup | 31198957 (31198728: failed pulling the image, rerun) |
| sim: container, real, real2, compare | 31198958, 31198959, 31198960, 31198961 |
| invivo: container, real, real2, compare | 31198962, 31198963, 31198964, 31198965 |
| `heidi-v1` (container timed out; compared afterwards on its outputs) | 31154793–31154801, compares 31198601, 31198602 |
