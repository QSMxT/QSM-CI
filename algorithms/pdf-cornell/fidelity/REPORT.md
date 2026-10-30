# pdf-cornell fidelity report

QSMxT/QSM-CI#300: does the `pdf-cornell` container compute what the authors' MATLAB computes? The check is
the shared harness [`fidelity/matlab/`](../../../fidelity/matlab/README.md) with this algorithm's
[`config.sh`](config.sh); rerun it whenever `recon.m`, its dependencies or the image change.

- **Checked:** 2026-10-30, on Slurm compute nodes, 8 CPUs per job.
- **Licensed MATLAB:** 23.2.0.2459199 (R2023b) Update 5, with the real toolboxes.
- **Image checked:** `ghcr.io/astewartau/qsm-ci/matlab-medi@sha256:bfff9adf6acd0001a408322d113ab29353af1eb22dcb84a9fa5fd2af26d5fb34` (`pdf-v1`).
  - `recon` is compiled with that licensed R2023b against the real toolboxes, with no shims.
  - It runs on the R2023b MATLAB Runtime (23.2.0.3097123 (R2023b) Update 11) under Apptainer.
- **Sources:** MEDI toolbox 2024.11.26 (`PDF.m`, `Fit_ppm_complex.m`, `dipole_kernel.m`, `dipole_term.m`, `cgsolve.m`).
- **Cases:**
  - `sim`: QSM-CI's in-silico head (QSM Challenge 2.0 simulation: 7 T, 4 echoes, 1 mm, 164×205×205), its ground-truth total field and its magnitude.
  - `invivo`: one EMTP travelling-head acquisition (`s005001-cbic-prisma-bridge-run1`: 3 T, 5 echoes, 1 mm, 184×256×128), the total field derived once with QSMxT v10.0.0 (ROMEO; `fidelity/matlab/make_cases.sh`) and its magnitude.

## Result: identical

| Output | sim: container vs real | invivo: container vs real | real2 vs real (sim, invivo) |
|---|---|---|---|
| `localfield.nii.gz` | identical | identical | identical |
| `intermediates/ifreq.nii.gz` | identical | identical | identical |
| `intermediates/n_std.nii.gz` | identical | identical | identical |
| `intermediates/rdf.nii.gz` | identical | identical | identical |

NRMSE and max |Δ| are 0 and no voxel differs wherever a cell says identical; binary maps have Dice 1.
The container and the licensed runs all used 8 threads (recorded in `intermediates.json`).

**Where the functions resolved** (`intermediates.json`): the MEDI functions resolve to the bundled `deps/medi` (2024.11.26) in the container's extracted archive and in licensed MATLAB; `padarray` to the Runtime's and the licensed installation's `toolbox/images/images`. The build's
`unresolvedSymbols.txt` and `mccExcludedFiles.log` list nothing, and `requiredMCRProducts.txt` lists
35002, 35003, 35010, 35117.

## Slurm jobs

| What | Job ids |
|---|---|
| Compile | 31109993 |
| Setup | 31117947 |
| sim: container, real, real2, compare | 31117948, 31117949, 31117950, 31117951 |
| invivo: container, real, real2, compare | 31117952, 31117953, 31117954, 31117955 |
