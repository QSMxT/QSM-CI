# tfi-cornell fidelity report

QSMxT/QSM-CI#300: does the `tfi-cornell` container compute what the authors' MATLAB computes? The check is
the shared harness [`fidelity/matlab/`](../../../fidelity/matlab/README.md) with this algorithm's
[`config.sh`](config.sh); rerun it whenever `recon.m`, its dependencies or the image change.

- **Checked:** 2026-10-30, on Slurm compute nodes, 8 CPUs per job.
- **Licensed MATLAB:** 23.2.0.2459199 (R2023b) Update 5, with the real toolboxes.
- **Image checked:** `ghcr.io/astewartau/qsm-ci/matlab-medi@sha256:ba6b3eb2c7c410cd1f66544dd455060a2da32ab76b9d9029e0b7b9345fb69565` (`tfi-v1`).
  - `recon` is compiled with that licensed R2023b against the real toolboxes, with no shims.
  - It runs on the R2023b MATLAB Runtime (23.2.0.3097123 (R2023b) Update 11) under Apptainer.
- **Sources:** MEDI toolbox 2024.11.26 (`MEDI_L1.m` and the helpers it reaches, `Fit_ppm_complex.m`).
- **Cases:**
  - `sim`: QSM-CI's in-silico head (7 T, 4 echoes, 1 mm, 164×205×205), its ground-truth total field and its magnitude.
  - `invivo`: one EMTP travelling-head acquisition (3 T, 5 echoes, 1 mm, 184×256×128), the total field derived once with QSMxT v10.0.0 (ROMEO) and its magnitude.

## Result: identical

| Output | sim: container vs real | invivo: container vs real | real2 vs real (sim, invivo) |
|---|---|---|---|
| `chimap.nii.gz` | identical | identical | identical |
| `intermediates/rdf.nii.gz` | identical | identical | identical |
| `intermediates/n_std.nii.gz` | identical | identical | identical |
| `intermediates/imag.nii.gz` | identical | identical | identical |
| `intermediates/p.nii.gz` | identical | identical | identical |

NRMSE and max |Δ| are 0 and no voxel differs wherever a cell says identical; binary maps have Dice 1.
The container and the licensed runs all used 8 threads (recorded in `intermediates.json`).

**Where the functions resolved** (`intermediates.json`): `MEDI_L1`, `parse_QSM_input`, `gradient_mask`, `dataterm_mask`, `cgsolve`, `reg_MEDI`, `dipole_kernel` and `Fit_ppm_complex` resolve to the bundled `deps/medi` (2024.11.26) in the container and in licensed MATLAB. The build's
`unresolvedSymbols.txt` and `mccExcludedFiles.log` list nothing, and `requiredMCRProducts.txt` lists
35002, 35003, 35010, 35117.

`MEDI_L1` ran with `'lambda',1000,'nosmv','linear',1,'percentage',0.9,'data_weighting',1,'cg_max_iter',100,'cg_tol',0.01,'max_iter',10,'tol_norm_ratio',0.1,'merit'` (recorded in `intermediates.json`), and logged "Preconditioning used", "Using linear formulation" and "Epsilon scaled with P". Gauss-Newton stopped at `tol_norm_ratio` after 4 iterations in silico and 5 in vivo.

## Slurm jobs

| What | Job ids |
|---|---|
| Compile | 31109995 |
| Setup | 31118026 |
| sim: container, real, real2, compare | 31118027, 31118028, 31118029, 31118030 |
| invivo: container, real, real2, compare | 31118031, 31118032, 31118033, 31118034 |
