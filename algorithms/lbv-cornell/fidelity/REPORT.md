# lbv-cornell fidelity report

QSMxT/QSM-CI#300: does the `lbv-cornell` container compute what the authors' MATLAB computes? The check is
the shared harness [`fidelity/matlab/`](../../../fidelity/matlab/README.md) with this algorithm's
[`config.sh`](config.sh); rerun it whenever `recon.m`, its dependencies or the image change.

- **Checked:** 2026-10-30, on Slurm compute nodes, 8 CPUs per job.
- **Licensed MATLAB:** 23.2.0.2459199 (R2023b) Update 5, with the real toolboxes.
- **Image checked:** `ghcr.io/astewartau/qsm-ci/matlab-medi@sha256:aceec8964177fbce20e46635632be6ae167d6cd395c5e65a3030198ea25fff1f` (`lbv-v1`).
  - `recon` is compiled with that licensed R2023b against the real toolboxes, with no shims.
  - It runs on the R2023b MATLAB Runtime (23.2.0.3097123 (R2023b) Update 11) under Apptainer.
- **Sources:** MEDI toolbox 2024.11.26 (`_LBV/LBV.m`, and `_LBV/mexMGv6.cpp` compiled with R2023b's `mex` and g++; BUILD.md).
- **Cases:**
  - `sim`: QSM-CI's in-silico head (7 T, 1 mm, 164×205×205), its ground-truth total field.
  - `invivo`: one EMTP travelling-head acquisition (3 T, 1 mm, 184×256×128), the total field derived once with QSMxT v10.0.0 (ROMEO).

## Result: identical

| Output | sim: container vs real | invivo: container vs real | real2 vs real (sim, invivo) |
|---|---|---|---|
| `localfield.nii.gz` | identical | identical | identical |
| `intermediates/ifreq.nii.gz` | identical | identical | identical |
| `intermediates/fl.nii.gz` | identical | identical | identical |
| `intermediates/lbv_interior.nii.gz` | identical | identical | identical |

NRMSE and max |Δ| are 0 and no voxel differs wherever a cell says identical; binary maps have Dice 1.
The container and the licensed runs all used 8 threads (recorded in `intermediates.json`).

**Where the functions resolved** (`intermediates.json`): `LBV` and `mexMGv6` resolve to the bundled `deps/medi` in the container (the mex compiled at build time) and to the assembled `deps/medi` in licensed MATLAB (the same source, compiled by the setup job). The build's
`unresolvedSymbols.txt` and `mccExcludedFiles.log` list nothing, and `requiredMCRProducts.txt` lists
35000, 35002, 35003, 35010.

**The shipped mex is not used.** The toolbox's `_LBV/mexMGv6.mexa64` predates its `mexMGv6.cpp`: called as `LBV.m` calls it, `[tmp, interior] = mexMGv6(...)`, it fails with "One or more output arguments not assigned during call to mexMGv6" (it returns no `interior`). The source does return it, so the build and the licensed runs compile `mexMGv6.cpp`; the container and licensed MATLAB then agree exactly.

## Slurm jobs

| What | Job ids |
|---|---|
| Compile | 31117712 (31109994: the shipped mexa64; 31113478: before a comment fix in recon.m) |
| Setup | 31120056 |
| sim: container, real, real2, compare | 31120057, 31120058, 31120059, 31120060 |
| invivo: container, real, real2, compare | 31120061, 31120062, 31120063, 31120064 |
