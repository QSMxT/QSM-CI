# resharp fidelity report

QSMxT/QSM-CI#300: does the `resharp` container compute what the authors' MATLAB computes? The check is
the shared harness [`fidelity/matlab/`](../../../fidelity/matlab/README.md) with this algorithm's
[`config.sh`](config.sh); rerun it whenever `recon.m`, its dependencies or the image change.

- **Checked:** 2026-10-30, on Slurm compute nodes, 8 CPUs per job.
- **Licensed MATLAB:** 23.2.0.2459199 (R2023b) Update 5, with the real toolboxes.
- **Image checked:** `ghcr.io/astewartau/qsm-ci/resharp@sha256:b147f71e433555c8be550195d16451caa191dacbcbccd3e392e200db8e0d7e2d` (`v1`).
  - `recon` is compiled with that licensed R2023b against the real toolboxes, with no shims.
  - It runs on the R2023b MATLAB Runtime (23.2.0.3097123 (R2023b) Update 11) under Apptainer.
- **Sources:** github.com/sunhongfu/QSM c75b138 (`background_field_removal/resharp.m`).
- **Cases:**
  - `sim`: QSM-CI's in-silico head (QSM Challenge 2.0 simulation: 7 T, 1 mm, 164×205×205), its ground-truth total field.
  - `invivo`: one EMTP travelling-head acquisition (`s005001-cbic-prisma-bridge-run1`: 3 T, 1 mm, 184×256×128), the total field derived once with QSMxT v10.0.0 (ROMEO; `fidelity/matlab/make_cases.sh`).

## Result: identical in vivo; a float-rounding residual in silico

| Output | sim: container vs real | invivo: container vs real | real2 vs real (sim, invivo) |
|---|---|---|---|
| `localfield.nii.gz` (float32) | NRMSE 1.48e-8 %, max \|Δ\| 9.3e-10 ppm, 142 of 6 892 100 voxels | identical | identical |
| `intermediates/localfield_f64.nii.gz` | NRMSE 1.26e-10 %, max \|Δ\| 6.4e-14 ppm, 1 118 223 voxels | identical | identical |
| `intermediates/resharp_mask.nii.gz` | identical (Dice 1) | identical (Dice 1) | identical |

NRMSE and max |Δ| are 0 and no voxel differs wherever a cell says identical.
The container and the licensed runs all used 8 threads (recorded in `intermediates.json`), and licensed MATLAB is
bit-repeatable (real2 = real). Both runs report the same residual and regularisation norms to 10 digits
(`res_term` 0.01852885243, `reg_term` 9.21658884), so CGS took the same path; the float64 fields differ by
~1e-14 relative, a few ulps.

**Cause: the container's operating system, not MATLAB.** `resharp-v2`, the same `recon` on the Update 5 Runtime
(`containers.mathworks.com/matlab-runtime:r2023b-update-5@sha256:4071c142…`, the licensed build 23.2.0.2459199), gives
the same numbers as `v1` on Update 11 (jobs 31200795–31200799), so `v1` stays. For LSQR, which shows the same
in-silico-only pattern, the licensed installation's libraries run inside the image's Ubuntu 22.04 userland reproduce
the container exactly, and the compiled binary on the RHEL 9 host reproduces licensed MATLAB (`lsqr`'s REPORT.md): a
system library under MATLAB, most likely glibc's libm, not MATLAB itself. The residual shows only on the in-silico
grid (164×205×205, two odd dimensions); the in-vivo grid (184×256×128) is identical.

**Where the functions resolved** (`intermediates.json`): `resharp` resolves to the bundled `deps/sun` in the
container's extracted archive and in licensed MATLAB; `padarray` and `cgs` to the Runtime's
`toolbox/images/images` and `toolbox/matlab/sparfun` in the container and to the licensed installation's in MATLAB.
The build's `unresolvedSymbols.txt` and `mccExcludedFiles.log` list nothing, and `requiredMCRProducts.txt` lists
35002, 35003, 35010, 35117.

`radius` 3 mm, `lambda` 1e-4 and 200 CGS iterations (`resharp.m`'s defaults) in both cases.

## Slurm jobs

| What | Job ids |
|---|---|
| Compile | 31123586 |
| Setup | 31158309 (31135468, 31151575: failed setups, rerun) |
| sim: container, real, real2, compare | 31158310, 31158311, 31158312, 31158313 |
| invivo: container, real, real2, compare | 31158314, 31158315, 31158316, 31158317 |
| `resharp-v2` on the Update 5 Runtime (setup, sim and invivo container + compare) | 31200795–31200799 |
