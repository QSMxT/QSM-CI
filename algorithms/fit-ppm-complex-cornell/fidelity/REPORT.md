# fit-ppm-complex-cornell fidelity report

QSMxT/QSM-CI#300: does the `fit-ppm-complex-cornell` container compute what the authors' MATLAB computes? The check is
the shared harness [`fidelity/matlab/`](../../../fidelity/matlab/README.md) with this algorithm's
[`config.sh`](config.sh); rerun it whenever `recon.m`, its dependencies or the image change.

- **Checked:** 2026-10-30, on Slurm compute nodes, 8 CPUs per job.
- **Licensed MATLAB:** 23.2.0.2459199 (R2023b) Update 5, with the real toolboxes.
- **Image checked:** `ghcr.io/astewartau/qsm-ci/matlab-medi@sha256:7efa4bd641b8311ac97a8a09dd438290f998f8163219b2f5d7ecae777a59811c` (`fitppm-v1`).
  - `recon` is compiled with that licensed R2023b against the real toolboxes, with no shims.
  - It runs on the R2023b MATLAB Runtime (23.2.0.3097123 (R2023b) Update 11) under Apptainer.
- **Sources:** MEDI toolbox 2024.11.26 (`Fit_ppm_complex.m`, `unwrapPhase.m`, `arlo.m`, and `mexUnwrap.c` compiled with R2023b's `mex` and gcc; BUILD.md).
- **Cases:**
  - `sim`: QSM-CI's in-silico head (QSM Challenge 2.0 simulation: 7 T, 4 echoes 4/12/20/28 ms, 1 mm, 164×205×205), its contract inputs.
  - `invivo`: one EMTP travelling-head acquisition (`s005001-cbic-prisma-bridge-run1`: 3 T, 5 echoes 5–29 ms, 1 mm, 184×256×128), its contract inputs.

## Result: identical

| Output | sim: container vs real | invivo: container vs real | real2 vs real (sim, invivo) |
|---|---|---|---|
| `totalfield.nii.gz` | identical | identical | identical |
| `intermediates/imag.nii.gz` | identical | identical | identical |
| `intermediates/ifreq_raw.nii.gz` | identical | identical | identical |
| `intermediates/n_std.nii.gz` | identical | identical | identical |
| `intermediates/ifreq.nii.gz` | identical | identical | identical |
| `intermediates/totalfield_f64.nii.gz` | identical | identical | identical |
| `intermediates/r2star.nii.gz` | identical | identical | identical |

NRMSE and max |Δ| are 0 and no voxel differs wherever a cell says identical; binary maps have Dice 1.
The container and the licensed runs all used 8 threads (recorded in `intermediates.json`).

**Where the functions resolved** (`intermediates.json`): `Fit_ppm_complex`, `unwrapPhase`, `mexUnwrap` and `arlo` resolve to the bundled `deps/medi` in the container (the mex compiled at build time) and to the assembled `deps/medi` in licensed MATLAB. The build's
`unresolvedSymbols.txt` and `mccExcludedFiles.log` list nothing, and `requiredMCRProducts.txt` lists
35000, 35002, 35003, 35010.

`intermediates/r2star.nii.gz` is ARLO's R2* (`arlo(TE, abs(iField))`, MEDI's `README.m:133`), so ARLO is checked too. `mexUnwrap` is compiled from the shipped `mexUnwrap.c`, as `lbv-cornell` compiles `mexMGv6` (the toolbox's `mexUnwrap.mexa64` does load, but `mexMGv6.mexa64` predates its source, so both mex files are built from source).

## Slurm jobs

| What | Job ids |
|---|---|
| Compile | 31117713 (31109996, 31113479: earlier builds) |
| Setup | 31120065 |
| sim: container, real, real2, compare | 31120066, 31120067, 31120068, 31120069 |
| invivo: container, real, real2, compare | 31120070, 31120071, 31120072, 31120073 |
