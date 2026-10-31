# laplacian-sti fidelity report

QSMxT/QSM-CI#300: does the `laplacian-sti` container compute what the authors' MATLAB computes? The check
is the shared harness [`fidelity/matlab/`](../../../fidelity/matlab/README.md) with this algorithm's
[`config.sh`](config.sh); rerun it whenever `recon.m`, its dependencies or the image change.

- **Checked:** 2026-10-30, on Slurm compute nodes, 8 CPUs per job.
- **Licensed MATLAB:** 23.2.0.2459199 (R2023b) Update 5, with the real toolboxes.
- **Image checked:** `ghcr.io/astewartau/qsm-ci/matlab-sti-laplacian@sha256:f27a6ddcaa60b9c59519784928da0f1be01e1756cc6623ac8fad3e8e9237fc91` (`v1`).
  - `recon` is compiled with that licensed R2023b against the real toolboxes, with no shims.
  - It runs on the R2023b MATLAB Runtime (23.2.0.3097123 (R2023b) Update 11) under Apptainer.
- **Sources:** STI Suite 3.0 `Core_Functions_P` (`MRPhaseUnwrap.p` and the helpers it calls: `fftnc`, `ifftnc`).
- **Cases:**
  - `sim`: QSM-CI's in-silico head (QSM Challenge 2.0 simulation: 7 T, 4 echoes, 1 mm, 164×205×205), its wrapped multi-echo phase.
  - `invivo`: one EMTP travelling-head acquisition (`s005001-cbic-prisma-bridge-run1`: 3 T, 5 echoes, 1 mm, 184×256×128), its wrapped multi-echo phase.

## Result: identical

| Output | sim: container vs real | invivo: container vs real | real2 vs real (sim, invivo) |
|---|---|---|---|
| `totalfield.nii.gz` | identical | identical | identical |
| `intermediates/unwrapped.nii.gz` | identical | identical | identical |
| `intermediates/laplacian.nii.gz` | identical | identical | identical |
| `intermediates/totalfield_f64.nii.gz` | identical | identical | identical |

NRMSE and max |Δ| are 0 and no voxel differs wherever a cell says identical.
The container and the licensed runs all used 8 threads (recorded in `intermediates.json`).

**Where the functions resolved** (`intermediates.json`): `MRPhaseUnwrap` is the bundled pcode; `padarray`, the one
toolbox function its pcode reaches (found by profiling a licensed run, `submit.sh laplacian-sti trace`, job
31123802, and named in `recon.m`'s `%#function` pragma), resolves to the Runtime's `toolbox/images/images` in the
container and to the licensed installation's in MATLAB. The build's `unresolvedSymbols.txt` and
`mccExcludedFiles.log` list nothing, and `requiredMCRProducts.txt` lists 35000, 35002, 35003, 35010, 35117, 35180.

`padsize` 12 (the function's default) in both cases; the echo combination divides the summed unwrapped echoes by
the summed echo times (`sum_TE` 0.064 s in silico), as STI Suite's QSM_GUI does.

## Slurm jobs

| What | Job ids |
|---|---|
| Trace | 31123802 |
| Compile | 31135504 (31128224: an earlier build) |
| Setup | 31154784 |
| sim: container, real, real2, compare | 31154785, 31154786, 31154787, 31154788 |
| invivo: container, real, real2, compare | 31154789, 31154790, 31154791, 31154792 |
