# qsmart-matlab fidelity report

QSMxT/QSM-CI#295, steps 1–2: does the `qsmart-matlab` container compute what the authors' MATLAB
computes? To rerun the check, see [`README.md`](README.md) (the shared harness in `fidelity/matlab/`).

- **Checked:** 2026-10-31, on Slurm compute nodes, 8 CPUs per job.
- **Licensed MATLAB:** 23.2.0.2459199 (R2023b) Update 5, with Image Processing Toolbox 23.2.
- **Image checked:** `ghcr.io/astewartau/qsm-ci/matlab-qsmart` `v4` (image ID
  `sha256:d27caa66b40247e3a7d14b45bc3bb39f85428c25da93bb5f90ed5de92748effc`; registry digest
  pending the push, then pinned in `algorithm.yml`).
  - `recon` is compiled with that licensed R2023b against the **real** Image Processing Toolbox,
    with no shims (build job 31200811; `recon` sha256 `9773c43e…`).
  - It runs on the R2023b MATLAB Runtime (23.2.0.3097123, Update 11) under Apptainer.
- **N4:** every run uses the image's own `N4BiasFieldCorrection` (ANTs 2.5.4).
- **Cases:**
  - `sim`: QSM-CI's in-silico head (QSM Challenge 2.0 simulation: 7 T, 4 echoes, 1 mm,
    164×205×205).
  - `invivo`: one EMTP travelling-head acquisition (3 T, 5 echoes, 184×256×128, with a mask
    that touches the field of view).

## Result: identical

**Every output of the `v4` container is bit-identical to the same `recon.m` run in licensed
MATLAB with the real toolboxes, in both cases.** That covers every intermediate and the final χ.
NRMSE and max |Δ| are 0, the masks have Dice 1, and no voxel differs.

| Output | In vivo: container vs real | In silico: container vs real | real2 vs real (both cases) |
|---|---|---|---|
| vessel mask `vasc_only` | identical (Dice 1) | identical (Dice 1) | identical |
| bottom-hat | identical | identical | identical |
| vesselness | identical | identical | identical |
| R_0 | identical (no rejects) | identical (Dice 1) | identical |
| total field | identical | identical | identical |
| stage-1 local field, χ | identical | identical | identical |
| stage-2 local field, χ | identical | identical | identical |
| **final χ** | **identical** | **identical** | identical |

The Otsu threshold on the vesselness is 0 in every run, as in the authors' code.

**Where the toolbox functions resolved.** `recon.m` records this in `intermediates.json`:
- in the container, `graythresh`, `imbothat`, `imclose`, `imdilate`, `imerode`, `imfilter`,
  `imgaussfilt3`, `imopen`, `padarray` and `strel` all resolve to
  `/opt/matlabruntime/R2023b/mcr/toolbox/images/images/`;
- `prctile` resolves to `…/toolbox/matlab/datafun/`, since it has been core MATLAB since R2022b;
- in licensed MATLAB, the same functions resolve to its `toolbox/images/images/` and
  `toolbox/matlab/datafun/`.

STI Suite's `.p` code reaches the same functions, which `recon.m` names in a `%#function` pragma
because mcc cannot trace into pcode. The build's `unresolvedSymbols.txt` and
`mccExcludedFiles.log` are empty, and every function is deployable. `requiredMCRProducts.txt`
lists 35000 35002 35003 35010 (Image Processing) 35117 35180.

**Thread count still matters.** The comparison holds at a fixed thread count. In the v2 check,
licensed MATLAB at 2 threads vs 8 changed the final χ by about 1.5e-4 % NRMSE (iLSQR); masks and
fields were identical. Here the container and the licensed runs all used 8 threads (recorded in
`intermediates.json`). The Runtime (Update 11) and the licensed MATLAB (Update 5) differ in update
level, with no effect on any output.

**Against the authors' own code, unpadded.** `v4` runs on the matrix as given, as the authors'
`QSMART.m` does (v1–v3 zero-padded odd dims to even, which the authors' code never does;
astewartau/QSM.rs#320). The authors' QSMART v1.0 was also run verbatim in the same licensed R2023b
on the same `sim` inputs (only N4 swapped for the image's binary, as above;
`/scratch/user/uqaste15/qsmart-parity/sim-odd/qsmart_odd_ci.m` on Bunya). Every intermediate of the
`v4` container is identical to it (vessel mask Dice 1, total field, R_0, both local fields and both
χ: max |Δ| 0); the final χ differs only by its float32 output rounding (max |Δ| 4.3e-9 ppm).

**What dropping the padding changed.** `sim` (164×205×205): the final χ moves by 14.3 % NRMSE from
`v3`. The padding had changed the vessel mask (Dice 0.988), the Laplacian-unwrapped total field
(1.8 %), R_0, both SDF stages and both inversions. `invivo` (184×256×128, all even): `v4` is
bit-identical to `v3`.

**Jobs (v4).** setup 31201202; sim: container 31201203, real 31201204, real2 31201205, compare
31201206; invivo: 31201207–31201210. Both `runs-<case>.md` read PASS.

**Fidelity record.** `algorithm.yml` records this under `fidelity:`, with the tolerance
`identical`.

**Rechecked with the shared harness (v3).** The same check, run again on 2026-10-28 through
`fidelity/matlab/` (QSMxT/QSM-CI#300) against the same `v3` digest, is again identical in every
output, in both cases (setup 30729509; container 30729510 and 30729514; real, real2 and compare
30729961–30729966).

## Deliberate deviations from the authors' code

These are kept in every run, so they don't affect the comparison. The full diff against the
originals is `$FID_WORK/reports/deviations.diff`.

- `calculate_curvature.m`: guards `max(abs(GC(GC<0)))` for when there are no negative
  curvatures. The original divides by an empty array.
- `vasculature_mask.m` → `vasculature_mask_qsmci.m`:
  - runs `N4BiasFieldCorrection` directly instead of `module load ants/1.9.v4; …`, and falls back
    with a warning if it's missing;
  - doesn't run `mex eig3volume.c` at run time (it's compiled at build time);
  - doesn't write debug NIfTIs;
  - can return the intermediates as a second output.
- `FrangiFilter3D.m`: a stray `keyboard` is commented out.

## Slurm jobs (v3)

| What | Job ids |
|---|---|
| Compile | 30727525 |
| Setup and pull | 30727583 |
| sim: container, real, real2, compare | 30727587–30727590 |
| invivo: container, real, real2, compare | 30727591–30727594 |

Container wall time was 3.5 min (invivo) and 5.4 min (sim), with a peak RSS of 4.5 GB. Licensed
`recon.m` took 258–307 s.

## History: v1 and v2 (toolbox shims)

The earlier images ran on toolbox shims, which are now removed from this algorithm. The per-shim
harness (`shim_fidelity.m`, and the `trace` run that checked every shim call against the
toolbox) was removed with them. It is in this PR's history at commit 34883c5
(`algorithms/qsmart-matlab/fidelity/`).

The same border bug is still in the shim copies of six other containers: `ilsqr-sti`,
`star-sti`, `vsharp-sti`, `chisep-ilsqr`, `chisep-medi` and `ukb-qsm`. Their `imdilate`/`imerode`
wrap round via `circshift`.

### v2 summary

`v2` is `sha256:682a369f5d9bf47870fc911d091e2a9f0ea2c463e8260ba477463660aedcc27a`: R2023b, the
border-fixed shims, and the N4 output kept single. It was checked on 2026-10-27.

- **The `v2` container computes what licensed MATLAB with the same code computes, bit for bit.**
  Every intermediate and the final χ are identical to licensed R2023b running `recon.m` with the
  shims.
- **Against licensed MATLAB with the real toolboxes, `v2` matches closely.** The final χ
  differs by 0.090 % NRMSE in vivo (max 0.015 ppm) and 0.235 % in silico (max 0.033 ppm). The
  vessel masks differ in 3 and 4 voxels (Dice 0.999998). Everything else upstream of the vessel
  mask is identical, apart from 1e-13 % rounding in the stage-1 local field.
- **All 11 shims pass** against the real toolboxes. The one remaining difference is `imfilter` on
  single-precision input (the Frangi Gaussian smoothing). It is at most 5e-7 relative, which is a
  few float32 ulps from a different summation order.
- **Why such a small rounding difference moves a few voxels:** the Otsu threshold on the
  vesselness is 0 in both cases, in every run. Any voxel with vesselness above 0 becomes a vessel,
  so float32 rounding decides the edge voxels. The authors' code behaves the same way. This
  sensitivity is the whole of the remaining difference.
- **Thread count alone moves the real-toolbox χ by about 1.5e-4 %** (8 vs 2 threads, iLSQR).
  Licensed MATLAB is bit-for-bit repeatable at a fixed thread count.
- **Two fixes, both in this PR, got here from `v1`:**
  - the morphology shims mishandled the volume border;
  - `vasculature_mask_qsmci.m` cast N4's float32 output to double, unlike the authors' code.
  
  The pinned `v1` image differed from licensed MATLAB by 6.2 % in vivo and 1.9 % in silico
  (see v1 below).

### v2 tolerance

`v2` passed with these tolerances. `v3` replaced it with the bar set at identical output:

| Comparison | Tolerance | In vivo | In silico |
|---|---|---|---|
| Container vs licensed MATLAB with the shims | identical | identical | identical |
| Container vs licensed MATLAB with the real toolboxes: final χ | NRMSE ≤ 0.5 % | 0.090 % | 0.235 % |
| Container vs licensed MATLAB with the real toolboxes: masks | Dice ≥ 0.9999 | 0.999998 (vessels), R_0 identical | 0.999998 (vessels), R_0 identical |
| Shims vs toolboxes | identical, or float rounding (see Step 1) | all pass | all pass |

The χ tolerance is looser than the 2.5e-4 % / 0.018 % that the fixed shims reached when the vessel
mask ran in double precision. With the authors' single precision, the remaining `imfilter`
rounding reaches the Otsu-0 vessel mask, and making it bit-exact would mean reproducing IPT's
internal summation order. One alternative is to compile the real IPT `imfilter` into the binary
instead of the shim, since the build MATLAB has IPT. That's a design change left open.

### Step 1: shims vs the real toolboxes

`shim_fidelity.m` calls each shim and its toolbox function on the same inputs, in the forms
QSMART, Frangi and STI Suite use them: 3-D volumes, even and odd sizes, masks touching the FOV,
sphere radii 1, 2, 5 and 8, logical, double, and single where the original runs single.

Pass rules:
- identical results for `strel`, `padarray`, the morphology functions and `graythresh`;
- max relative error ≤ 1e-10 for `imfilter`/`imgaussfilt3` (≤ 1e-5 on single-precision input);
- max relative error ≤ 1e-12 for `prctile`.

Forms that a shim doesn't support and QSMART doesn't use are reported as INFO and not scored:
`strel('disk')`, `padarray` replicate/symmetric/circular, 3-D `imfilter` kernels, and matrix
`prctile`.

| Shim | Status | Cases | Worst error |
|---|---|---|---|
| `graythresh` | PASS | 8 | identical |
| `imbothat` | PASS | 3 | identical |
| `imclose` | PASS | 5 | identical |
| `imdilate` | PASS | 7 | identical |
| `imerode` | PASS | 7 | identical |
| `imfilter` | PASS | 11 | rel 2.2e-7 (single input), 1.1e-15 (double) |
| `imgaussfilt3` | PASS | 10 | rel 1.3e-15 |
| `imopen` | PASS | 4 | identical |
| `padarray` | PASS | 6 | identical |
| `prctile` | PASS | 5 | rel 2.9e-15 |
| `strel` | PASS | 4 | identical |

### Step 2: container vs licensed MATLAB

Each case runs `recon.m` four ways:

| Run | What |
|---|---|
| `container` | `v2` under Apptainer, as `qsm_ci/containers.py` runs it, with `QSMCI_INTERMEDIATES` set |
| `real`, `real2` | licensed MATLAB with the real toolboxes, without `shims/` on the path, run twice |
| `trace` | licensed MATLAB with the shims; every shim call also runs the toolbox function and logs the difference |

How to read the tables:
- NRMSE is 100·‖a − b‖/‖b‖ inside the brain mask, with b the reference run.
- Max |Δ| is taken over the whole volume.
- Dice is for the vessel set (mask & ~`vasc_only`) and the R_0 reject set (mask & ~`R_0`).
- χ and fields are in ppm.

| Output | In vivo: container vs real | In vivo: container vs trace | In silico: container vs real | In silico: container vs trace | real2 vs real |
|---|---|---|---|---|---|
| vessel mask `vasc_only` | Dice 0.999998 (3 voxels) | identical | Dice 0.999998 (4 voxels) | identical | identical |
| bottom-hat | identical | identical | identical | identical | identical |
| vesselness | 0.0025 %, max 1e-5 | identical | 0.018 %, max 6e-8 | identical | identical |
| R_0 | identical (no rejects) | identical | identical (Dice 1) | identical | identical |
| total field | identical | identical | identical | identical | identical |
| stage-1 local field | 3e-13 %, max 7e-16 | identical | 3e-13 %, max 4e-16 | identical | identical |
| stage-1 χ | 1.6e-4 %, max 8e-7 | identical | 1.4e-4 %, max 6e-7 | identical | identical |
| stage-2 local field | 0.082 %, max 0.0058 | identical | 0.15 %, max 0.0053 | identical | identical |
| stage-2 χ | 0.23 %, max 0.0071 | identical | 0.51 %, max 0.017 | identical | identical |
| **final χ** | **0.090 %, max 0.015** | **identical** | **0.235 %, max 0.033** | **identical** | identical |

`trace` vs `real` is the same as `container` vs `real`, since the container and `trace` are
identical.

**Thread-count floor.** `real` at 2 threads vs 8 threads:

| Output | In vivo | In silico |
|---|---|---|
| masks and fields | identical | identical |
| stage-1 χ | 1.6e-4 % | 1.5e-4 % |
| stage-2 χ | 2.6e-4 % | 1.3e-4 % |
| final χ | 1.6e-4 % | 1.4e-4 % |

**Every shim call in the pipeline** (429 calls in vivo, 417 in silico) was compared with the
toolbox on the same arguments. All of them are identical, except:
- `imfilter` in the Frangi `imgaussian`: 36 calls, max rel 5.4e-7, on single input;
- `imgaussfilt3` in `sdf_curvature`/`calculate_curvature`: 361 calls, max 1.6e-15, on double.

**The single-precision change matches the authors' code path.** Licensed MATLAB with the real
toolboxes and the new `vasculature_mask_qsmci.m` (N4 output kept single) is bit-identical, in
every intermediate and in both cases, to the earlier run that emulated the authors' single
precision by patching the cast out.

### v1

The first check ran against `v1`:
- image: `sha256:437824e7fc0511b35c69e0f265ac04601109186efd4d589c09eea1c0416360a5`;
- R2026a Runtime;
- the original shims;
- N4 output cast to double.

Its final χ differed from licensed MATLAB with the real toolboxes by 6.22 % NRMSE in vivo
(max 0.079) and 1.89 % in silico (max 0.029). The vessel mask Dice was 0.9934 in vivo.

**Shim bugs (fixed in this PR).** Five shims failed: `imdilate`, `imerode`, `imclose`, `imopen`
and `imbothat`. These were real bugs, not harness artefacts.

IPT treats voxels beyond the volume as background for dilation (−Inf, or false) and as foreground
for erosion (+Inf). The shims didn't:
- the greyscale `imdilate`/`imerode` used `circshift` with no padding, so values wrapped round
  from the opposite face;
- `imclose` closed against the edge.

The fix pads by the structuring element's radius with IPT's border value, then crops. With it,
all 11 shims are identical to the toolbox on every case.

Where the bugs reached QSMART:
- **every face of the volume:** the vessel bottom-hat (worst case: max 0.553, in-mask 0.523);
- **masks touching the FOV:** `QSMART_SDF`'s closing and `calculate_curvature`'s dilation;
- **every dataset:** STI Suite `FastQSM`'s `imclose(kernel, [1 1 1])` on its 7×7×7 kernel.

Minimal repro, where the `shim_*` functions are the old shims loaded with
`fidelity_shim_copies`:

```matlab
se = strel('sphere', 1); sse = shim_strel('sphere', 1);
A = zeros(5, 5, 5); A(1, 3, 3) = 1;          % bright voxel on the x = 1 face
D = imdilate(A, se); S = shim_imdilate(A, sse);
[D(5, 3, 3), S(5, 3, 3)]                     % [0 1]: the old shim wrapped x = 1 round to x = 5
B = ones(5, 5, 5); B(1, 3, 3) = 0;
D = imerode(B, se);  S = shim_imerode(B, sse);
[D(5, 3, 3), S(5, 3, 3)]                     % [1 0]
M = true(7, 7, 7); M(1, 4, 4) = false;       % a hole on the border face
D = imclose(M, se);  S = shim_imclose(M, sse);
[D(1, 4, 4), S(1, 4, 4)]                     % [0 1]: IPT treats beyond-border voxels as background
```

**One harness artefact (fixed).** The first harness held `imfilter` on single-precision input to
the double-precision tolerance of 1e-10.

**Shim fix with the double-precision vessel mask.** The fixed shims, run with the vessel mask
still in double, matched licensed MATLAB to 2.5e-4 % in vivo and 0.018 % in silico. With
`v1`'s double cast, the real-toolbox χ differed from the authors' single-precision path by
0.26 % in vivo and 11.3 % in silico (vessel Dice 0.9931).

**The Runtime itself was never a source of difference.** `v1` matched licensed MATLAB with the
same shims to 1e-6 % across R2026a vs R2023b. `v2` is identical to it.

### Slurm jobs (v1, v2)

| What | Job ids |
|---|---|
| Compile of `v2`'s `recon` | 30717941 |
| Setup and pull of `v2` | 30718776 |
| Shims | 30718777 |
| Runs and compare (sim): container, real, real2, trace, compare | 30718778–30718782 |
| Runs and compare (invivo): container, real, real2, trace, compare | 30718783–30718787 |
| Thread-count floor | 30720727, 30720728 |
| Single-precision check | 30718791 |
| `v1` runs | 30711163–30711174, 30713269–30713299, 30714390–30714391 |

Container wall time is about 4–5 min, with a peak RSS of 4.5 GB.
