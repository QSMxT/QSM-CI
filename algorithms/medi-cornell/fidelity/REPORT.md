# medi-cornell fidelity report

QSMxT/QSM-CI#300: does the `medi-cornell` container compute what the authors' MATLAB computes? The check
is the shared harness [`fidelity/matlab/`](../../../fidelity/matlab/README.md) with this algorithm's
[`config.sh`](config.sh); rerun it whenever `recon.m`, its dependencies or the image change.

- **Checked:** 2026-10-28, on Slurm compute nodes, 8 CPUs per job.
- **Licensed MATLAB:** 23.2.0.2459199 (R2023b) Update 5, with the real toolboxes.
- **Image checked:** `ghcr.io/astewartau/qsm-ci/matlab-medi@sha256:122ac0095b1472b80f4e5441be2dd87fb6d730c101663365fb88be747ebd24f4` (`v3`).
  - `recon` is compiled with that licensed R2023b against the real toolboxes, with no shims.
  - It runs on the R2023b MATLAB Runtime (23.2.0.3097123 (R2023b) Update 11) under Apptainer.
- **Previous image:** `ghcr.io/astewartau/qsm-ci/matlab-medi@sha256:3747339b38bb93294bbe07c3c5f1b4882ce675b6e57d473e0148b224afd6186d` (`v2`).
- **Cases:**
  - `sim`: QSM-CI's in-silico head (QSM Challenge 2.0 simulation: 7 T, 4 echoes, 1 mm, 164×205×205), its ground-truth local field.
  - `invivo`: one EMTP travelling-head acquisition (`s005001-cbic-prisma-bridge-run1`: 3 T, 5 echoes, 1 mm, 184×256×128), with the local field and eroded mask derived once with QSMxT v10.0.0 (ROMEO, V-SHARP; `fidelity/matlab/make_cases.sh`).

## Result: identical

| Output | sim: container vs real | invivo: container vs real | real2 vs real (sim, invivo) |
|---|---|---|---|
| `chimap.nii.gz` | identical | identical | identical |
| `intermediates/imag.nii.gz` | identical | identical | identical |
| `intermediates/n_std.nii.gz` | identical | identical | identical |
| `intermediates/rdf.nii.gz` | identical | identical | identical |

NRMSE and max |Δ| are 0 and no voxel differs wherever a cell says identical. The container and the
licensed runs all used 8 threads (recorded in `intermediates.json`).

**Where the MEDI functions resolved** (`intermediates.json`): `MEDI_L1`, `parse_QSM_input`,
`gradient_mask`, `dataterm_mask` and `cgsolve` resolve to the bundled `deps/medi` (2024.11.26) in
the container's extracted archive, and to the assembled `deps/medi` in licensed MATLAB.
The build's `unresolvedSymbols.txt` and `mccExcludedFiles.log` list nothing, and `requiredMCRProducts.txt` lists 35002, 35003, 35010, 35117.

## Which MEDI the previous image held

`v2` holds **not** MEDI 2024.11.26 but the Oct-2024 GitHub copy of the toolbox
(`huawu02/MEDI_toolbox` at `83c1960`, 2024-10-08, the copy in `~/code/MEDI_toolbox` on Bunya and in
`~/code/ref/medi/MEDI_toolbox` on the workstation). That copy's `MEDI_L1` and `parse_QSM_input`
differ from 2024.11.26, which also turns SMV and merit on by default. The evidence: `v2` against the
same `recon.m` (main's, `lambda` 100) in licensed R2023b with each toolbox:

| Case | `v2` vs licensed + Oct-2024 copy | `v2` vs licensed + 2024.11.26 |
|---|---|---|
| sim | NRMSE 0.00025 %, max 2.7e-5 ppm | NRMSE 132 % |
| invivo | NRMSE 0.0036 %, max 4.5e-4 ppm | NRMSE 111 % |

The remaining difference to the Oct-2024 copy is rounding: `v2` was compiled with R2026a and runs on
the R2026a Runtime, against licensed R2023b here (the voxels differ in the last digits, everywhere).
`v2` therefore failed the identical bar on both counts, and `v3` was built.

## What changed in v3

- **MEDI 2024.11.26**, the release QSM.rs's MEDI port follows.
- **`lambda` defaults to Cornell's 1000** (was 100). `recon.m` puts the field on a fixed reference
  scale (3 T, 8 ms), so one `lambda` serves every field strength.
- **`nosmv` / `nomerit` passed explicitly.** 2024.11.26's `parse_QSM_input` turns SMV and merit on
  unless told otherwise; QSM-CI's `smv_radius` and `merit` stay off by default, as before.
- Compiled with licensed R2023b on the R2023b Runtime; `recon.m` writes what `MEDI_L1` reads
  (`RDF`, `N_std`, `iMag`) and its arguments with `QSMCI_INTERMEDIATES`.
- No pcode, so no `%#function` pragma: mcc traces every call. `requiredMCRProducts.txt` lists the
  Image Processing Toolbox (35010) from static analysis of MEDI's other functions; the profiled
  licensed run reaches no toolbox function outside core MATLAB.


## Slurm jobs

| What | Job ids |
|---|---|
| Compile | 30730311 |
| Setup and pull | 30731582 |
| sim: container, real, real2, compare | 30731583, 30731584, 30731585, 30731586 |
| invivo: container, real, real2, compare | 30731587, 30731588, 30731589, 30731590 |
| v2 check (main's `recon.m`): licensed + 2024.11.26 (sim, invivo) | 30731460, 30731462 |
| v2 check: licensed + Oct-2024 copy (sim, invivo) | 30731465, 30731467 |
| v2 check: `v2` container (sim, invivo) | 30729995, 30729999 |
| v2 check: compares | 30731564–30731567 |
