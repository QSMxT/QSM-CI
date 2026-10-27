# star-sti fidelity report

QSMxT/QSM-CI#300: does the `star-sti` container compute what the authors' MATLAB computes? The check
is the shared harness [`fidelity/matlab/`](../../../fidelity/matlab/README.md) with this algorithm's
[`config.sh`](config.sh); rerun it whenever `recon.m`, its dependencies or the image change.

- **Checked:** 2026-10-28, on Slurm compute nodes, 8 CPUs per job.
- **Licensed MATLAB:** 23.2.0.2459199 (R2023b) Update 5, with the real toolboxes.
- **Image checked:** `ghcr.io/astewartau/qsm-ci/matlab-sti-star@sha256:77674d0ef999060e6b9afcaea022a69d277958cad40435f8c113b7bc1ea02b84 (`v2`)`.
  - `recon` is compiled with that licensed R2023b against the real toolboxes, with no shims.
  - It runs on the R2023b MATLAB Runtime (23.2.0.3097123 (R2023b) Update 11) under Apptainer.
- **Previous image:** `ghcr.io/astewartau/qsm-ci/matlab-sti-star@sha256:5815b4190a7ca10a1dd789dc099e20dda4db1304794e81ba36a45ef67077ff8f (`v1`)`.
- **Cases:**
  - `sim`: QSM-CI's in-silico head (QSM Challenge 2.0 simulation: 7 T, 4 echoes, 1 mm, 164×205×205), its ground-truth local field.
  - `invivo`: one EMTP travelling-head acquisition (`s005001-cbic-prisma-bridge-run1`: 3 T, 5 echoes, 1 mm, 184×256×128), with the local field and eroded mask derived once with QSMxT v10.0.0 (ROMEO, V-SHARP; `fidelity/matlab/make_cases.sh`).

## Result: identical

| Output | sim: container vs real | invivo: container vs real | real2 vs real (sim, invivo) |
|---|---|---|---|
| `chimap.nii.gz` | identical | identical | identical |
| `intermediates/tissue_phase.nii.gz` | identical | identical | identical |

NRMSE and max |Δ| are 0 and no voxel differs wherever a cell says identical. The container and the
licensed runs all used 8 threads (recorded in `intermediates.json`).

**Where the toolbox functions resolved** (`intermediates.json`): in the container, `padarray` resolves to the Runtime's `toolbox/images/images`; in licensed MATLAB, to the same folders of its own installation.
The build's `unresolvedSymbols.txt` and `mccExcludedFiles.log` list nothing, and `requiredMCRProducts.txt` lists 35000, 35002, 35003, 35010, 35117, 35180.

## What changed from v1

`v1` was compiled with R2026a against the free Runtime, with our own re-implementations of the Image
Processing Toolbox functions STI Suite calls (`shims/`). Their greyscale `imdilate`/`imerode` wrapped
round at the volume border via `circshift` (the bug #296 found in qsmart-matlab's copies). `v2` drops
the shims: `recon` is compiled with licensed R2023b against the real toolbox, and `recon.m` names the
functions STI Suite's pcode calls in a `%#function` pragma, since mcc can't trace into pcode. They
were found by profiling a licensed run (`submit.sh <slug> trace`). `v1` was not rerun: its shims are
gone from this folder.

`QSM_star` also reaches code outside `Core_Functions_P`, which the profile shows: the operator
classes in `Support_Functions/qsm_kiwi_1` (`@iFDF`, `@suscepMap`, `@TVOP_3Dnew`) and `soft` from
`Support_Functions/SpaRSA`. Both are bundled (BUILD.md §1). The only toolbox function it reaches is
`padarray`.


## Slurm jobs

| What | Job ids |
|---|---|
| Compile | 30729321 |
| Setup and pull | 30729967 |
| sim: container, real, real2, compare | 30729968, 30729969, 30729970, 30729971 |
| invivo: container, real, real2, compare | 30729972, 30729973, 30729974, 30729975 |
