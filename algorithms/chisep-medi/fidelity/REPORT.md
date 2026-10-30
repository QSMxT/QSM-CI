# chisep-medi fidelity report

QSMxT/QSM-CI#300: does the `chisep-medi` container compute what the authors' MATLAB computes? The check
is the shared harness [`fidelity/matlab/`](../../../fidelity/matlab/README.md) with this algorithm's
[`config.sh`](config.sh); rerun it whenever `recon.m`, its dependencies or the image change.

- **Checked:** 2026-10-28, on Slurm compute nodes, 8 CPUs per job.
- **Licensed MATLAB:** 23.2.0.2459199 (R2023b) Update 5, with the real toolboxes.
- **Image checked:** `ghcr.io/astewartau/qsm-ci/chi-sep-medi@sha256:06ffc17a55223b05eb1442d9092b751b64a50e0e39320602a289b5c2ca9d2615` (`v2`).
  - `recon` is compiled with that licensed R2023b against the real toolboxes, with no shims.
  - It runs on the R2023b MATLAB Runtime (23.2.0.3097123 (R2023b) Update 11) under Apptainer.
- **Previous image:** `ghcr.io/astewartau/qsm-ci/chi-sep-medi@sha256:d1f5e3ecb92c9153983c5d82c135cf50e451387a21d5814bdfdd10edc238a5d5` (`v1`).
- **Cases:**
  - `chisep-mc`: QSM-CI's default χ-separation phantom (7 T, 8 echoes, 1 mm, 164×205×205).
  - `invivo`: one EMTP travelling-head acquisition (`s005001-cbic-prisma-bridge-run1`: 3 T, 5 echoes, 1 mm, 184×256×128), with the local field, eroded mask, χ and R2′ (0.52·R2*) derived once with QSMxT v10.0.0 (`fidelity/matlab/make_cases.sh`).

## Result: identical

| Output | chisep-mc: container vs real | invivo: container vs real | real2 vs real (chisep-mc, invivo) |
|---|---|---|---|
| `chi-dia.nii.gz` | identical | identical | identical |
| `chi-para.nii.gz` | identical | identical | identical |
| `intermediates/local_field_hz.nii.gz` | identical | identical | identical |
| `intermediates/x_tot.nii.gz` | identical | identical | identical |

NRMSE and max |Δ| are 0 and no voxel differs wherever a cell says identical. The container and the
licensed runs all used 8 threads (recorded in `intermediates.json`).

**Where the toolbox functions resolved** (`intermediates.json`): in the container, `hann`, `hanning`, `imclose`, `imdilate`, `imerode`, `imopen`, `padarray`, `strel`, `tukeywin` resolve to the Runtime's `toolbox/images/images`, `toolbox/signal/signal`; in licensed MATLAB, to the same folders of its own installation.
The build's `unresolvedSymbols.txt` and `mccExcludedFiles.log` list nothing, and `requiredMCRProducts.txt` lists 35000, 35002, 35003, 35010, 35108, 35117, 35180.

## What changed from v1

`v1` was compiled with R2026a against the free Runtime, with our own re-implementations of the Image
Processing and Signal Processing toolbox functions the pcode calls (`shims/`: `padarray`, `strel`,
greyscale `imdilate`/`imerode` that wrapped round at the volume border, `imclose`, `imopen`,
`tukeywin`, `hann`, `hanning`). `v2` drops them: `recon` is compiled with licensed R2023b against
the real toolboxes, and `recon.m` names the functions the pcode calls in a `%#function` pragma
(found by profiling a licensed run, plus the rest of the old shim set). `v1` was not rerun: its
shims are gone from this folder.

**Path order.** The χ-separation toolbox comes first on the path, as its own scripts and the v1
build put it. Its `utils/` carries pcode copies of the NIfTI loaders (`load_untouch_nii` and
friends) and a `medfilt3`, which shadow Jimmy Shen's and the Image Processing Toolbox's;
`recon.m` reads its inputs through them (`resolution.txt` of each licensed run).

**Toolbox source.** The SNU-LIST χ-separation toolbox is obtained through its Google Form and is
not public. The copy used (`functions/`, `utils/`; files dated 2025-07-02, the v1.1.3 that v1's
BUILD.md names) is on Bunya at `/scratch/project_mnt/S0169/uqaste15_exp/matlab-fidelity/src/chisep-toolbox`,
copied from `/scratch/user/uqaste15/chisep_ilsqr/toolbox`.

**MEDI toolbox.** v2 bundles Cornell's MEDI toolbox 2024.11.26 (the release QSM.rs's MEDI port
follows), its top-level functions only, without `MEDI_L1ss*`: its `bet2/` calls `mex` and
`MEDI_L1ss*` calls the Symbolic Math Toolbox's `heaviside`, neither of which can be deployed. In the
profiled licensed run `chi_sep_MEDI` reaches no MEDI function at all (its solver and its gradient
operators are inside `chi_sep_MEDI_func.p`), so the MEDI release doesn't change this output. Its
log prints `res_norm_ratio: 0.0000` from the first Gauss-Newton iteration on both cases, in the
container and in licensed MATLAB alike; the outputs are non-zero.


## Slurm jobs

| What | Job ids |
|---|---|
| Compile | 30729495 |
| Setup and pull | 30729985 |
| chisep-mc: container, real, real2, compare | 30729986, 30729987, 30729988, 30729989 |
| invivo: container, real, real2, compare | 30729990, 30729991, 30729992, 30729993 |
