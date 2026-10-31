# chisep-medi fidelity report

QSMxT/QSM-CI#300: does the `chisep-medi` container compute what the authors' MATLAB computes? The check
is the shared harness [`fidelity/matlab/`](../../../fidelity/matlab/README.md) with this algorithm's
[`config.sh`](config.sh); rerun it whenever `recon.m`, its dependencies or the image change.

- **Checked:** 2026-10-31 (`v4`), on Slurm compute nodes, 8 CPUs per job. `v3` was checked earlier
  the same day, `v2` on 2026-10-28.
- **Licensed MATLAB:** 23.2.0.2459199 (R2023b) Update 5, with the real toolboxes.
- **Image checked:** `ghcr.io/astewartau/qsm-ci/chi-sep-medi@sha256:c3afb14130929cb73fd41d9011afcce69634969b73216e996341e9c946fc8d7c` (`v4`).
  - `recon` is compiled with that licensed R2023b against the real toolboxes, with no shims, from
    this folder's `recon.m` (build job 31198842; `recon` sha256 `47e5864a…35213ea12`, the same file in
    the image and in the build).
  - It runs on the R2023b MATLAB Runtime (23.2.0.3097123 (R2023b) Update 11) under Apptainer.
  - The `.sif` was pulled from GHCR by the pinned digest (config `sha256:fa6bc55a7af1…`, the local
    build's image id).
- **Licensed code:** the same `recon.m` (`N_std` from `Fit_ppm_complex`, `params.time_limit = Inf`,
  `mask_CSF = []`) with the same χ-separation toolbox, MEDI 2024.11.26 and NIfTI sources as before.
- **Previous images:** `v3` `sha256:6cec1e895428f02b4e87cb2b744ca53fdc7146f6280882ca2785bec22a60586b`
  (identical to licensed MATLAB on 2026-10-31; `N_std` = ones); `v2`
  `sha256:06ffc17a55223b05eb1442d9092b751b64a50e0e39320602a289b5c2ca9d2615` (identical to licensed
  MATLAB on 2026-10-28, but with an all-false CSF mask the solver returned its initial guess, #315);
  `v1` `sha256:d1f5e3ecb92c9153983c5d82c135cf50e451387a21d5814bdfdd10edc238a5d5`.
- **Cases:**
  - `chisep-mc`: QSM-CI's default χ-separation phantom (7 T, 8 echoes, 1 mm, 164×205×205).
  - `invivo`: one EMTP travelling-head acquisition (`s005001-cbic-prisma-bridge-run1`: 3 T, 5 echoes, 1 mm, 184×256×128), with the local field, eroded mask, χ and R2′ (0.52·R2*) derived once with QSMxT v10.0.0 (`fidelity/matlab/make_cases.sh`).

## Result: identical

| Output | chisep-mc: container vs real | invivo: container vs real | real2 vs real (chisep-mc, invivo) |
|---|---|---|---|
| `chi-dia.nii.gz` | identical | identical | identical |
| `chi-para.nii.gz` | identical | identical | identical |
| `intermediates/local_field_hz.nii.gz` | identical | identical | identical |
| `intermediates/n_std.nii.gz` | identical | identical | identical |
| `intermediates/x_tot.nii.gz` | identical | identical | identical |

NRMSE and max |Δ| are 0 and no voxel differs wherever a cell says identical. The container and the
licensed runs all used 8 threads (recorded in `intermediates.json`). `v3`'s check (without
`n_std`) and `v2`'s gave the same table.

**MEDI iterates.** Every `v4` run, container and licensed alike, runs 6 Gauss-Newton iterations with
the same residual ratios: `res_norm_ratio` 0.168 at iteration 1 to 0.0297 at 6 on `chisep-mc`, 0.151
to 0.0205 on `invivo`. In licensed MATLAB, `Fit_ppm_complex` resolves to MEDI 2024.11.26's
(`resolution.txt`).

**Where the toolbox functions resolved** (`intermediates.json`): in the container, `hann`, `hanning`, `imclose`, `imdilate`, `imerode`, `imopen`, `padarray`, `strel`, `tukeywin` resolve to the Runtime's `toolbox/images/images`, `toolbox/signal/signal`; in licensed MATLAB, to the same folders of its own installation.
The build's `unresolvedSymbols.txt` and `mccExcludedFiles.log` list nothing, and `requiredMCRProducts.txt` lists 35000, 35002, 35003, 35010, 35108, 35117, 35180.

## What changed from v3

Two source changes, in `recon.m`; the licensed runs use the same `recon.m`.

- **`N_std`** was ones. It is now MEDI `Fit_ppm_complex`'s a-priori error of the fitted frequency,
  `dp1 = sqrt(S0 / (S0·S2 − S1²))` with `S_j = Σ_k |M_k|² k^j` over echoes `k = 0…n−1`, zero outside
  the mask. `dp1` depends on the magnitude only, so the stage needs no phase.
  - This is how the toolbox computes `N_std`. `Chisep_script.m` gets it from `Preprocessing4Phase`;
    the GUI (`WrapperChisepMEDI`) computes it from the multi-echo magnitude and zeroes it outside
    the brain mask. Probed in licensed R2023b with a stand-in app object and a spy `chi_sep_MEDI`
    (Bunya jobs 31198786, 31198847): on phantoms with a different decay in every voxel, the GUI's
    `N_std` and `Preprocessing4Phase`'s (with a random phase) both equal `Fit_ppm_complex`'s `dp1` to
    1.1·10⁻¹⁵ relative.
  - An earlier probe (2026-10-28) saw `N_std = 0.916/|mag|_RSS` and read it as `c/|mag|`. That
    phantom decayed the same way in every voxel, which makes `dp1` proportional to `1/|mag|_RSS`:
    `0.916` is `dp1·|mag|_RSS` for its four echoes. With per-voxel decay the ratio varies (0.72–0.87
    on a 5-echo phantom), and with one echo it is `√2`, as `Fit_ppm_complex`'s one-echo case gives.
  - `chi_sep_MEDI` normalises the weights `mask/N_std` by their mean, so only the shape of `N_std`
    matters, not its scale.
- **No wall-clock limit:** `params.time_limit = Inf`. The toolbox's default (1800 s) stops the
  Gauss-Newton loop after 30 minutes, so large inputs could give results that depend on the runner's
  speed. On a phantom that finishes below the limit, `Inf`, `1800` and the default are bit-identical
  and a 1 ms limit changes the output (job 31198787), so the field is the limit and `Inf` only
  removes it.
- `recon.m` also writes `N_std` as the intermediate `n_std.nii.gz`.

## What changed from v2

One source change, in `recon.m`: `option_data.mask_CSF = []` instead of `false(size(mask))`, and
`params.lambda_CSF = 1` (the GUI's value; unused without a CSF mask) instead of 0. With an all-false
mask the toolbox's CSF mean is NaN, every step became NaN and was rejected, and `chi_sep_MEDI`
returned its initial guess (QSMxT/QSM-CI#315). An empty mask is what the toolbox's own GUI passes
when it has none. The licensed runs use the same `recon.m`, so they are the authors' code with that
change.

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
log printed `res_norm_ratio: 0.0000` from the first Gauss-Newton iteration on both cases, in the
container and in licensed MATLAB alike: the all-false CSF mask, fixed in `v3`.


## Slurm jobs

`v4` (2026-10-31; work root `matlab-fidelity/v4chk` on Bunya):

| What | Job ids |
|---|---|
| Compile | 31198842 |
| `N_std` and `time_limit` probes | 31198786, 31198787, 31198847 |
| Pull by digest; setup | 31198874; 31198875 |
| chisep-mc: container, real, real2, compare | 31198876, 31198877, 31198878, 31198879 |
| invivo: container, real, real2, compare | 31198880, 31198881, 31198882, 31198883 |

`v3` (2026-10-31; work root `matlab-fidelity/v3chk` on Bunya):

| What | Job ids |
|---|---|
| Compile (2026-10-30) | 31163532 |
| Setup | 31191948 |
| chisep-mc: container, real, real2, compare | 31191949, 31191950, 31191951, 31191952 |
| invivo: container, real, real2, compare | 31191953, 31191954, 31191955, 31191956 |

`v2` (2026-10-28):

| What | Job ids |
|---|---|
| Compile | 30729495 |
| Setup and pull | 30729985 |
| chisep-mc: container, real, real2, compare | 30729986, 30729987, 30729988, 30729989 |
| invivo: container, real, real2, compare | 30729990, 30729991, 30729992, 30729993 |
