# hdqsm fidelity report

QSMxT/QSM-CI#300: does the `hdqsm` container compute what the authors' MATLAB computes? The check is
the shared harness [`fidelity/matlab/`](../../../fidelity/matlab/README.md) with this algorithm's
[`config.sh`](config.sh); rerun it whenever `recon.m`, its dependencies or the image change.

- **Checked:** 2026-10-30, on Slurm compute nodes, 8 CPUs per job.
- **Licensed MATLAB:** 23.2.0.2459199 (R2023b) Update 5, with the real toolboxes.
- **Image checked:** `ghcr.io/astewartau/qsm-ci/hd-qsm@sha256:79d3ecefcd9ad766502c8ef079bcb1a3408d658cfe27f50bfc6f0b61cba8cb92` (`v2`).
  - `recon` is compiled with that licensed R2023b against the real toolboxes, with no shims.
  - It runs on the R2023b MATLAB Runtime (23.2.0.3097123 (R2023b) Update 11) under Apptainer.
- **Sources:** github.com/mglambert/HD-QSM c456a94 (`HDQSM.m`); FANSI-toolbox 93044a3 (`dipole_kernel_angulated.m`).
- **Cases:**
  - `sim`: QSM-CI's in-silico head (QSM Challenge 2.0 simulation: 7 T, 4 echoes, 1 mm, 164×205×205), its ground-truth local field and its magnitude.
  - `invivo`: one EMTP travelling-head acquisition (`s005001-cbic-prisma-bridge-run1`: 3 T, 5 echoes, 1 mm, 184×256×128), with the local field and eroded mask derived once with QSMxT v10.0.0 (ROMEO, V-SHARP; `fidelity/matlab/make_cases.sh`) and its magnitude.

## Result: identical

| Output | sim: container vs real | invivo: container vs real | real2 vs real (sim, invivo) |
|---|---|---|---|
| `chimap.nii.gz` | identical | identical | identical |
| `intermediates/weight.nii.gz` | identical | identical | identical |
| `intermediates/x_unmasked.nii.gz` | identical | identical | identical |

NRMSE and max |Δ| are 0 and no voxel differs wherever a cell says identical; binary maps have Dice 1.
The container and the licensed runs all used 8 threads (recorded in `intermediates.json`).

**Where the functions resolved** (`intermediates.json`): `HDQSM` and `dipole_kernel_angulated` resolve to the bundled `deps/hdqsm` in the container's extracted archive and in licensed MATLAB. The build's
`unresolvedSymbols.txt` and `mccExcludedFiles.log` list nothing, and `requiredMCRProducts.txt` lists
35003, 35010.

Both stages ran their full count in both cases (20 L1 and 80 L2 iterations, recorded in `intermediates.json`).

## Slurm jobs

| What | Job ids |
|---|---|
| Compile | 31124509 |
| Setup | 31131134 |
| sim: container, real, real2, compare | 31131135, 31131136, 31131137, 31131138 |
| invivo: container, real, real2, compare | 31131139, 31131140, 31131141, 31131142 |
