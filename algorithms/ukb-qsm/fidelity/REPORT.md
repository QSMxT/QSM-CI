# ukb-qsm fidelity report

QSMxT/QSM-CI#300: does the `ukb-qsm` container compute what the authors' MATLAB computes? The check
is the shared harness [`fidelity/matlab/`](../../../fidelity/matlab/README.md) with this algorithm's
[`config.sh`](config.sh); rerun it whenever `recon.m`, its dependencies or the image change.

- **Checked:** 2026-10-28, on Slurm compute nodes, 8 CPUs per job.
- **Licensed MATLAB:** 23.2.0.2459199 (R2023b) Update 5, with the real toolboxes.
- **Image checked:** `ghcr.io/astewartau/qsm-ci/matlab-ukb-qsm@sha256:c8a50375ab0b69e8a928a07b1ecef51e533f7948c67b706434284ec6f1e3b9cf (`v2`)`.
  - `recon` is compiled with that licensed R2023b against the real toolboxes, with no shims.
  - It runs on the R2023b MATLAB Runtime (23.2.0.3097123 (R2023b) Update 11) under Apptainer.
- **Previous image:** `ghcr.io/astewartau/qsm-ci/matlab-ukb-qsm@sha256:a3aeab5ff603b95288c563a0499d355d8ac564281fae221959b014f644ffa5db (`v1`)`.
- **Cases:**
  - `sim`: QSM-CI's in-silico head (QSM Challenge 2.0 simulation: 7 T, 4 echoes, 1 mm, 164×205×205).
  - `invivo`: one EMTP travelling-head acquisition (`s005001-cbic-prisma-bridge-run1`: 3 T, 5 echoes, 1 mm, 184×256×128).

## Result: identical

| Output | sim: container vs real | invivo: container vs real | real2 vs real (sim, invivo) |
|---|---|---|---|
| `chimap.nii.gz` | identical | identical | identical |
| `intermediates/chimap.nii.gz` | identical | identical | identical |
| `intermediates/dB_vsf.nii.gz` | identical | identical | identical |
| `intermediates/map.nii.gz` | identical | identical | identical |
| `intermediates/map2.nii.gz` | identical | identical | identical |
| `intermediates/mask.nii.gz` | identical | identical | identical |
| `intermediates/mask_final.nii.gz` | identical | identical | identical |
| `intermediates/mask_vsharp.nii.gz` | identical | identical | identical |
| `intermediates/phs_comb.nii.gz` | identical | identical | identical |

NRMSE and max |Δ| are 0 and no voxel differs wherever a cell says identical. The container and the
licensed runs all used 8 threads (recorded in `intermediates.json`).

**Where the toolbox functions resolved** (`intermediates.json`): in the container, `bwareaopen`, `imclose`, `imdilate`, `imerode`, `imfill`, `padarray`, `strel` resolve to the Runtime's `toolbox/images/images`; in licensed MATLAB, to the same folders of its own installation.
The build's `unresolvedSymbols.txt` and `mccExcludedFiles.log` list nothing, and `requiredMCRProducts.txt` lists 35000, 35002, 35003, 35010, 35117, 35180.

## What changed from v1

`v1` was compiled with R2026a against the free Runtime, with our own re-implementations of the Image
Processing Toolbox functions: STI Suite's (`padarray`, `strel`, greyscale `imdilate`/`imerode`, which
wrapped round at the volume border via `circshift`, `imclose`, `imopen`) and the UKB code's own
`bwareaopen` and `imfill` (on a `qsmci_label` connected-component labeller). `v2` drops every shim:
`recon` is compiled with licensed R2023b against the real toolbox. The UKB code's `bwareaopen` and
`imfill` calls are traced by mcc; the functions STI Suite's pcode calls (`imclose`, `imdilate`,
`imerode`, `padarray`, `strel`, found by profiling a licensed run) are named in `recon.m`'s
`%#function` pragma. `v1` was not rerun: its shims are gone from this folder.

The intermediates come from a third output of `ukb/UKBiobank_QSM_core.m` that only copies values
out (lines marked `% EDIT (intermediates)`): both phase-variance maps, the trimmed mask, the
T2*-weighted combined phase, V-SHARP's local field and mask, the final mask and χ.


## Slurm jobs

| What | Job ids |
|---|---|
| Compile | 30729323 |
| Setup and pull | 30729572 |
| sim: container, real, real2, compare | 30729573, 30729574, 30729575, 30729576 |
| invivo: container, real, real2, compare | 30729577, 30729578, 30729579, 30729580 |
