# l1qsm fidelity report

QSMxT/QSM-CI#300: does the `l1qsm` container compute what the authors' MATLAB computes? The check is
the shared harness [`fidelity/matlab/`](../../../fidelity/matlab/README.md) with this algorithm's
[`config.sh`](config.sh); rerun it whenever `recon.m`, its dependencies or the image change.

- **Checked:** 2026-10-30, on Slurm compute nodes, 8 CPUs per job.
- **Licensed MATLAB:** 23.2.0.2459199 (R2023b) Update 5, with the real toolboxes.
- **Image checked:** `ghcr.io/astewartau/qsm-ci/l1-qsm@sha256:edb8c46ae324f34ce337eea4f7179f8d73267f5c21f1517a9041e28c449b2177` (`v2`).
  - `recon` is compiled with that licensed R2023b against the real toolboxes, with no shims.
  - It runs on the R2023b MATLAB Runtime (23.2.0.3097123 (R2023b) Update 11) under Apptainer.
- **Sources:** FANSI-toolbox 93044a3 (`Inversion/L1-QSM/nlL1TV.m`, `dipole_kernel_angulated.m`).
- **Cases:**
  - `sim`: QSM-CI's in-silico head (QSM Challenge 2.0 simulation: 7 T, 4 echoes 4/12/20/28 ms, 1 mm, 164×205×205), its ground-truth local field and its magnitude.
  - `invivo`: one EMTP travelling-head acquisition (`s005001-cbic-prisma-bridge-run1`: 3 T, 5 echoes 5–29 ms, 1 mm, 184×256×128), with the local field and eroded mask derived once with QSMxT v10.0.0 (ROMEO, V-SHARP; `fidelity/matlab/make_cases.sh`) and its magnitude.

## Result: identical

| Output | sim: container vs real | invivo: container vs real | real2 vs real (sim, invivo) |
|---|---|---|---|
| `chimap.nii.gz` | identical | identical | identical |
| `intermediates/phase_input.nii.gz` | identical | identical | identical |
| `intermediates/weight.nii.gz` | identical | identical | identical |
| `intermediates/x_rad.nii.gz` | identical | identical | identical |

NRMSE and max |Δ| are 0 and no voxel differs wherever a cell says identical; binary maps have Dice 1.
The container and the licensed runs all used 8 threads (recorded in `intermediates.json`).

**Where the functions resolved** (`intermediates.json`): `nlL1TV` and `dipole_kernel_angulated` resolve to the bundled `deps/fansi` (93044a3) in the container's extracted archive and in licensed MATLAB. The build's
`unresolvedSymbols.txt` and `mccExcludedFiles.log` list nothing, and `requiredMCRProducts.txt` lists
35002, 35003, 35010, 35180, 35380.

Run details (`intermediates.json`): 50 ADMM iterations in both cases (the maximum); `te` the first echo (4 ms, 5 ms). `isGPU` is false in every run, so the Parallel Computing Toolbox `gpuArray` path that mcc bundles (35180) is never taken.

## Slurm jobs

| What | Job ids |
|---|---|
| Compile | 31119215 |
| Setup | 31123480 |
| sim: container, real, real2, compare | 31123481, 31123482, 31123483, 31123484 |
| invivo: container, real, real2, compare | 31123485, 31123486, 31123487, 31123488 |
