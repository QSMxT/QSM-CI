# sharp-sepia fidelity report

QSMxT/QSM-CI#300: does the `sharp-sepia` container compute what SEPIA's SHARP computes in MATLAB? The
check is the shared harness [`fidelity/matlab/`](../../../fidelity/matlab/README.md) with this
algorithm's [`config.sh`](config.sh); rerun it whenever `recon.m`, its dependencies or the image change.

- **Checked:** 2026-10-28, on Slurm compute nodes, 8 CPUs per job.
- **Licensed MATLAB:** 23.2.0.2459199 (R2023b) Update 5, with the real Image Processing Toolbox.
- **Image checked:** `ghcr.io/astewartau/qsm-ci/matlab-sharp-sepia@sha256:3ad75137e636fac724356641b488ad8cec0f87bb67e7ae0aa1c290f70eac209e` (`v1`).
  - `recon` is compiled with that licensed R2023b against the real toolbox, with no shims.
  - It runs on the R2023b MATLAB Runtime (23.2.0.3097123 (R2023b) Update 11) under Apptainer.
- **Sources:** kschan0214/sepia `db939ccc1e9aa2d02c2dc0e6adb5ad2b1f0cc839` (`SHARP.m`, `zeropad_odd_dimension.m`); MEDI toolbox 2024.11.26 (`SMV.m`, `SMV_kernel.m`, `sphere_kernel.m`).
- **Cases:**
  - `sim`: QSM-CI's in-silico head (QSM Challenge 2.0 simulation: 7 T, 1 mm, 164×205×205, two odd axes), its ground-truth total field.
  - `invivo`: one EMTP travelling-head acquisition (`s005001-cbic-prisma-bridge-run1`: 3 T, 1 mm, 184×256×128), the total field derived once with QSMxT v10.0.0 (ROMEO; `fidelity/matlab/make_cases.sh`).

## Result: identical

| Output | sim: container vs real | invivo: container vs real | real2 vs real (sim, invivo) |
|---|---|---|---|
| `localfield.nii.gz` | identical | identical | identical |
| `intermediates/localfield_f64.nii.gz` | identical | identical | identical |
| `intermediates/sharp_mask.nii.gz` | identical | identical | identical |

NRMSE and max |Δ| are 0 and no voxel differs wherever a cell says identical. The container and the
licensed runs all used 8 threads (recorded in `intermediates.json`), and `SHARP.m`'s output was
real in every run (`isreal`).

**Where the functions resolved** (`intermediates.json`): SEPIA's and MEDI's files from the bundled
`deps/sepia` and `deps/medi`; `padarray` from the Runtime's `toolbox/images/images` in the container,
and from the same folder of the licensed installation. The build's `unresolvedSymbols.txt` and
`mccExcludedFiles.log` list nothing, and `requiredMCRProducts.txt` lists 35002, 35003, 35010, 35117.

## Is `recon.m` SEPIA's path?

SEPIA itself (the same commit, MEDI 2024.11.26) was run headless in the same licensed MATLAB:

- Its GUI, built with `sepia` and SHARP selected, exports `algorParam.bfr.radius = 4`,
  `algorParam.bfr.threshold = 0.03`, `refine_method = 'None'`, `erode_radius = 0`,
  `erode_before_radius = 0`. The panel labels the radius "SMV radius (voxel):".
- With that config, `BackgroundRemovalMacro` pads odd axes (`[33 29 25]` → `[34 30 26]`) and calls
  `SHARP(…, radius = 4, threshold = 0.03, voxel_size, matrix_size = [34 30 26])` (logged with a
  conditional breakpoint), and its output is identical (`isequal`) to padding, calling `SHARP.m`
  directly with 4 and 0.03, and cropping, which is what `recon.m` does.
- The radius is in mm: with voxels 0.9 × 1.0 × 1.3 mm, `sphere_kernel(…, 4)` reaches 4, 4 and 3
  voxels (3.6, 4.0, 3.9 mm) from the centre.
- `Wrapper_BFR_SHARP.m`'s fallbacks (radius 0.1, threshold 30) apply only to a config without
  the fields.
- `SMV`, `SMV_kernel` and `sphere_kernel` resolve to MEDI 2024.11.26 (MD5s in BUILD.md); SEPIA
  ships none of its own.

## Slurm jobs

| What | Job ids |
|---|---|
| SEPIA headless probe | 30816239 |
| Compile | 30816572 |
| Setup | 30818226 (the `.sif` was built on the workstation from the pushed image, since the new package is private until made public) |
| sim: container, real, real2, compare | 30818227, 30818228, 30818229, 30818230 |
| invivo: container, real, real2, compare | 30818231, 30818232, 30818233, 30818234 |
