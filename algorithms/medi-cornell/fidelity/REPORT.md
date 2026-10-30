# medi-cornell fidelity report

QSMxT/QSM-CI#300: does the `medi-cornell` container compute what the authors' MATLAB computes? The check
is the shared harness [`fidelity/matlab/`](../../../fidelity/matlab/README.md) with this algorithm's
[`config.sh`](config.sh); rerun it whenever `recon.m`, its dependencies or the image change.

- **Checked:** 2026-10-28, on Slurm compute nodes, 8 CPUs per job.
- **Licensed MATLAB:** 23.2.0.2459199 (R2023b) Update 5, with the real toolboxes and the MEDI toolbox 2024.11.26.
- **Image checked:** `ghcr.io/astewartau/qsm-ci/matlab-medi@sha256:b81527b0c5a49a39378700358dd3b0ada3a4a0ed5742715d0d699c99846f0278` (`v4`).
  - `recon` is compiled with that licensed R2023b against the real toolboxes, with no shims.
  - It runs on the R2023b MATLAB Runtime (23.2.0.3097123 (R2023b) Update 11) under Apptainer.
- **Settings:** `recon.m`'s defaults, which are `MEDI_L1`'s own (BUILD.md): `lambda` 1000, SMV 5 mm
  with mask shrinking, MERIT and the CSF zero reference (MEDI+0, `lambda_CSF` 100) on. `MEDI_L1`'s
  arguments, as recorded in `intermediates.json`:
  `'lambda',1000,'percentage',0.9,'data_weighting',1,'cg_max_iter',100,'cg_tol',0.01,'max_iter',10,'tol_norm_ratio',0.1,'smv',5,'smv_shrink_mask',1,'merit','lambda_CSF',100`.
- **Previous images:** `v3` `sha256:122ac0095b1472b80f4e5441be2dd87fb6d730c101663365fb88be747ebd24f4`,
  `v2` `sha256:3747339b38bb93294bbe07c3c5f1b4882ce675b6e57d473e0148b224afd6186d` (below).
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
| `intermediates/r2s.nii.gz` | identical | identical | identical |
| `intermediates/mask_csf.nii.gz` | identical (Dice 1) | identical (Dice 1) | identical |
| `intermediates/mask_inverted.nii.gz` | identical (Dice 1) | identical (Dice 1) | identical |

NRMSE and max |Δ| are 0 and no voxel differs wherever a cell says identical. The container and the
licensed runs all used 8 threads (recorded in `intermediates.json`).

Both cases run every default feature: `extract_CSF` finds a CSF mask (sim 6000 voxels, invivo 10787),
so `MEDI_L1` adds the CSF term; SMV erodes the mask (sim 1310617 → 988796 voxels, invivo
1390739 → 1051958); and Gauss-Newton stops after 5 iterations at `tol_norm_ratio` 0.1 in both.

**Where the MEDI functions resolved** (`intermediates.json`): `MEDI_L1`, `parse_QSM_input`,
`gradient_mask`, `dataterm_mask`, `cgsolve`, `Fit_ppm_complex`, `arlo`, `extract_CSF`, `reg_CSF`,
`SMV` and `sphere_kernel` resolve to the bundled `deps/medi` (2024.11.26) in the container's
extracted archive, and to the assembled `deps/medi` in licensed MATLAB. The build's
`unresolvedSymbols.txt` and `mccExcludedFiles.log` list nothing, and `requiredMCRProducts.txt` lists
35002, 35003, 35010, 35117 (`extract_CSF` calls the Image Processing Toolbox's `bwconncomp`).

## What changed in v4

`v3` ran MEDI 2024.11.26 with QSM-CI's old settings; `v4` runs it with the toolbox's own defaults,
those of `MEDI_L1` and of its pipeline script `README.m`. BUILD.md lists them and what `recon.m` does
for each.

- **SMV (5 mm, shrinking the mask) and MERIT on.** `recon.m` no longer passes `nosmv` / `nomerit`.
- **MEDI+0.** `recon.m` makes `Mask_CSF` as `README.m` does, `extract_CSF(arlo(TE, |echoes|), Mask,
  voxel_size)`, so `MEDI_L1` adds the CSF term (`lambda_CSF` 100). With fewer than three echoes, or
  when `extract_CSF` errors or finds nothing, it runs without it.
- **`N_std` from `Fit_ppm_complex`** on the echo magnitudes, as `README.m` (its noise estimate depends
  only on the magnitudes), instead of a 1/magnitude proxy.
- **The authors' units.** `CF` = 42.576 MHz/T · `B0` and `delta_TE` = `TE(2) − TE(1)` (`TE` for one
  echo), as `README.m` and `Read_DICOM`, instead of a fixed 3 T, 8 ms scale.
- **Every `MEDI_L1` option exposed** as a parameter, matching QSM.rs's `MediParams`.
- **Odd axes padded with SMV.** Without it, `MEDI_L1` diverges on the sim case's odd grid
  (164×205×205), in licensed MATLAB, with the same inputs and settings (`real-nopad`, the same
  `recon.m` without the odd-axis padding):

  | Run | vs | `chimap.nii.gz` NRMSE | max abs diff (ppm) | differing voxels |
  |---|---|---|---|---|
  | `real-nopad` | `real` | 12500 % | 64.6 | 999218 of 6892100 |

  Its Gauss-Newton `res_norm_ratio` rises to 9.8 by iteration 4 and it stops at `max_iter` 10, the
  data cost 25 times its first value; with padding it falls to 0.07 by iteration 5. The in vivo grid
  is even, so nothing is padded there.
- **`'zeropad'` done by `recon.m`.** `MEDI_L1`'s own `'zeropad'` errors in 2024.11.26 (`reg_MEDI`:
  "Arrays have incompatible sizes", because `parse_QSM_input` pads the volumes but not
  `opts.matrix_size`), so `recon.m` pads what it saves in `RDF.mat` and crops the result, as
  `'zeropad'` means to.
- **χ zero outside the inverted mask.** With the CSF term `MEDI_L1` subtracts the CSF mean from every
  voxel, including those outside the SMV-eroded mask; `recon.m` sets those back to 0.
- New intermediates: `r2s`, `mask_csf`, `mask_inverted`.

## History: v3

`v3` (`sha256:122ac0095b14…`) was identical to licensed R2023b + MEDI 2024.11.26 on the same cases,
with `lambda` 1000, `nosmv`, `nomerit`, no CSF term and the fixed 3 T, 8 ms scale.

### Which MEDI `v2` held

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

### What changed in v3

- **MEDI 2024.11.26**, the release QSM.rs's MEDI port follows.
- **`lambda` defaults to Cornell's 1000** (was 100). `recon.m` puts the field on a fixed reference
  scale (3 T, 8 ms), so one `lambda` serves every field strength.
- **`nosmv` / `nomerit` passed explicitly.** 2024.11.26's `parse_QSM_input` turns SMV and merit on
  unless told otherwise; QSM-CI's `smv_radius` and `merit` stayed off by default, as before (until `v4`).
- Compiled with licensed R2023b on the R2023b Runtime; `recon.m` writes what `MEDI_L1` reads
  (`RDF`, `N_std`, `iMag`) and its arguments with `QSMCI_INTERMEDIATES`.
- No pcode, so no `%#function` pragma: mcc traces every call. `requiredMCRProducts.txt` lists the
  Image Processing Toolbox (35010) from static analysis of MEDI's other functions; the profiled
  licensed run reaches no toolbox function outside core MATLAB.

## Slurm jobs

| What | Job ids |
|---|---|
| v4 compile | 30737861 |
| v4 setup and pull | 30738355 |
| v4 sim: container, real, real2, compare | 30738356, 30738357, 30738358, 30738359 |
| v4 invivo: container, real, real2, compare | 30738360, 30738361, 30738362, 30738363 |
| v4 sim without odd-axis padding: setup, real-nopad, compare | 30738364, 30738365, 30738366 |
| v3 compile | 30730311 |
| v3 setup and pull | 30731582 |
| v3 sim: container, real, real2, compare | 30731583, 30731584, 30731585, 30731586 |
| v3 invivo: container, real, real2, compare | 30731587, 30731588, 30731589, 30731590 |
| v2 check (main's `recon.m`): licensed + 2024.11.26 (sim, invivo) | 30731460, 30731462 |
| v2 check: licensed + Oct-2024 copy (sim, invivo) | 30731465, 30731467 |
| v2 check: `v2` container (sim, invivo) | 30729995, 30729999 |
| v2 check: compares | 30731564–30731567 |
