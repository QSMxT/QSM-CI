# iharperella-sti fidelity report

QSMxT/QSM-CI#300: does the `iharperella-sti` container compute what the authors' MATLAB computes? The check is
the shared harness [`fidelity/matlab/`](../../../fidelity/matlab/README.md) with this algorithm's
[`config.sh`](config.sh); rerun it whenever `recon.m`, its dependencies or the image change.

- **Checked:** 2026-10-30, on Slurm compute nodes, 8 CPUs per job.
- **Licensed MATLAB:** 23.2.0.2459199 (R2023b) Update 5, with the real toolboxes.
- **Image checked:** `ghcr.io/astewartau/qsm-ci/matlab-sti-iharperella@sha256:40af0c6187c5e57484e9deeba283ef8f37257bd35ee722db8ff415f0923edd65` (`v2`).
  - `recon` is compiled with that licensed R2023b against the real toolboxes, with no shims.
  - It runs on the R2023b MATLAB Runtime (23.2.0.3097123 (R2023b) Update 11) under Apptainer.
- **Sources:** STI Suite 3.0 `Core_Functions_P` (`iHARPERELLA.p` and the helpers it calls: `SMVFiltering`, `ball3D`, `fftnc`, `ifftnc`).
- **Cases:**
  - `sim`: QSM-CI's in-silico head (QSM Challenge 2.0 simulation: 7 T, 1 mm, 164×205×205), its ground-truth total field.
  - `invivo`: one EMTP travelling-head acquisition (`s005001-cbic-prisma-bridge-run1`: 3 T, 1 mm, 184×256×128), the total field derived once with QSMxT v10.0.0 (ROMEO; `fidelity/matlab/make_cases.sh`).

## Result: identical

| Output | sim: container vs real | invivo: container vs real | real2 vs real (sim, invivo) |
|---|---|---|---|
| `localfield.nii.gz` | identical | identical | identical |
| `intermediates/iharperella_unmasked.nii.gz` | identical | identical | identical |

NRMSE and max |Δ| are 0 and no voxel differs wherever a cell says identical; binary maps have Dice 1.
The container and the licensed runs all used 8 threads (recorded in `intermediates.json`).

**Where the functions resolved** (`intermediates.json`): `iHARPERELLA` is the bundled pcode; `padarray`, the one toolbox function its pcode reaches (found by profiling a licensed run, `submit.sh iharperella-sti trace`, job 31123801, and named in `recon.m`'s `%#function` pragma), resolves to the Runtime's `toolbox/images/images` in the container and to the licensed installation's in MATLAB. The build's
`unresolvedSymbols.txt` and `mccExcludedFiles.log` list nothing, and `requiredMCRProducts.txt` lists
35000, 35002, 35003, 35010, 35117, 35180.

`niter` 40 and `padsize` 0 (the function's defaults) in both cases.

## Slurm jobs

| What | Job ids |
|---|---|
| Trace | 31123801 |
| Compile | 31129270 (31128223: before a comment fix in recon.m) |
| Setup | 31135064 |
| sim: container, real, real2, compare | 31135065, 31135066, 31135067, 31135068 |
| invivo: container, real, real2, compare | 31135069, 31135070, 31135071, 31135072 |
