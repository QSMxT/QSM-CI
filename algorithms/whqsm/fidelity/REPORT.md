# whqsm fidelity report

QSMxT/QSM-CI#300: does the `whqsm` container compute what the authors' MATLAB computes? The check is
the shared harness [`fidelity/matlab/`](../../../fidelity/matlab/README.md) with this algorithm's
[`config.sh`](config.sh); rerun it whenever `recon.m`, its dependencies or the image change.

- **Checked:** 2026-11-18, on Slurm compute nodes, 8 CPUs per job (`v2`: 2026-10-30).
- **Licensed MATLAB:** 23.2.0.2459199 (R2023b) Update 5, with the real toolboxes.
- **Image checked:** `ghcr.io/astewartau/qsm-ci/wh-qsm@sha256:8ac7798e437e0ef68e111d056a7381e976c471d3835099631b3eea5f95550be4` (`v3`).
  - `recon` is compiled with that licensed R2023b against the real toolboxes, with no shims.
  - It runs on the R2023b MATLAB Runtime (23.2.0.3097123 (R2023b) Update 11) under Apptainer.
- **Sources:** FANSI-toolbox 93044a3 (`Inversion/WH-QSM/WH_nlTV.m`, `dipole_kernel_angulated.m`), with
  QSM-CI's Newton-guard patch to `WH_nlTV.m` in both the container and the licensed runs
  (`../wh_nltv_newton_guard.patch`, [`../BUILD.md`](../BUILD.md)).
- **Cases:**
  - `sim`: QSM-CI's in-silico head (QSM Challenge 2.0 simulation: 7 T, 4 echoes 4/12/20/28 ms, 1 mm, 164×205×205), its ground-truth local field and its magnitude.
  - `invivo`: one EMTP travelling-head acquisition (`s005001-cbic-prisma-bridge-run1`: 3 T, 5 echoes 5–29 ms, 1 mm, 184×256×128), with the local field and eroded mask derived once with QSMxT v10.0.0 (ROMEO, V-SHARP; `fidelity/matlab/make_cases.sh`) and its magnitude.

## Result: identical

| Output | sim: container vs real | invivo: container vs real |
|---|---|---|
| `chimap.nii.gz` | identical | identical |
| `intermediates/phase_input.nii.gz` | identical | identical |
| `intermediates/x_rad.nii.gz` | identical | identical |

NRMSE and max |Δ| are 0 and no voxel differs wherever a cell says identical; binary maps have Dice 1.
The container and the licensed runs all used 8 threads (recorded in `intermediates.json`). `real2`
(the run-to-run floor) was identical to `real` for `v2` and was not repeated.

**Where the functions resolved** (`intermediates.json`): `WH_nlTV` and `dipole_kernel_angulated` resolve to the bundled `deps/fansi` (93044a3) in the container's extracted archive and in licensed MATLAB. The build's
`unresolvedSymbols.txt` and `mccExcludedFiles.log` list nothing, and `requiredMCRProducts.txt` lists
35002, 35003, 35010, 35180, 35380.

Run details (`intermediates.json`): 71 ADMM iterations in silico (stopped at `tolUpdate` 0.1) and 150 in vivo (the maximum); `te` the first echo (4 ms, 5 ms); flat weight (WH_nlTV.m's default). `isGPU` is false in every run, so the Parallel Computing Toolbox `gpuArray` path that mcc bundles (35180) is never taken.

## The Newton guard against `v2` (FANSI verbatim)

Each case run with the `v2` image, `v3` with the guard on (the default) and `v3` with
`newton_guard: false`. `pdf` is the input whose QSM-CI cells went NaN: the in-silico head's local
field from `pdf-qsmrs` (the `gt+pdf-qsmrs` cell).

| Case | v3, guard off, vs v2 | v3, guard on, vs v2 | NaN in the mask (v2 / off / on) |
|---|---|---|---|
| `sim` | identical | NRMSE 0.0001%, max abs diff 1.4e-6 ppm | 0 / 0 / 0 |
| `invivo` | identical | NRMSE 0.0001%, max abs diff 1.2e-6 ppm | 0 / 0 / 0 |
| `pdf` | identical (all NaN) | finite | all 1310617 / all / 0 |

With the guard off, `v3` reproduces `v2` bit for bit. With it on, maps that never went NaN still move
by about 1e-6 ppm: FANSI's Newton step sometimes overshoots before it converges, and the clamp changes
that path, not the solution. On `pdf` the guarded map agrees with QSM.rs's guarded port
(`whqsm-qsmrs` on the same cell): NRMSE 0.097%, correlation 1.0000, max abs diff 0.035 ppm.

## Slurm jobs

| What | Job ids |
|---|---|
| Compile | 33146536 |
| Runtime image to .sif | 33147010 |
| Setup | 33147995 |
| sim: container, real, compare | 33147996, 33147997, 33147998 |
| invivo: container, real, compare | 33147999, 33148000, 33148001 |
| v2 / v3 guard on / v3 guard off: sim, invivo, pdf | 33148004, 33148005, 33148006 |
