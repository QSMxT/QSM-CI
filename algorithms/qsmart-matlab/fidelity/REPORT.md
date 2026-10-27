# qsmart-matlab fidelity report

QSMxT/QSM-CI#295, steps 1–2: does the `qsmart-matlab` container compute what the authors' MATLAB
computes? To rerun the check, see [`README.md`](README.md).

- **Checked:** 2026-10-27, on Slurm compute nodes.
- **Licensed MATLAB:** 23.2.0.2459199 (R2023b) Update 5, with Image Processing Toolbox 23.2 and
  Statistics and Machine Learning Toolbox 23.2.
- **Image checked:** `ghcr.io/astewartau/qsm-ci/matlab-qsmart@sha256:682a369f5d9bf47870fc911d091e2a9f0ea2c463e8260ba477463660aedcc27a`
  (`v2`). It was compiled with the same R2023b and runs on the R2023b MATLAB Runtime under
  Apptainer.
- **N4:** every run uses the image's own `N4BiasFieldCorrection` (ANTs 2.5.4), so N4 is not a
  source of difference.
- **Cases:**
  - `sim`: QSM-CI's in-silico head (QSM Challenge 2.0 simulation: 7 T, 4 echoes, 1 mm,
    164×205×205).
  - `invivo`: one EMTP travelling-head acquisition (3 T, 5 echoes, 184×256×128, with a mask
    that touches the field of view).

## Summary

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
  (see [History](#history-v1)).

## Tolerance and verdict

**PASS.** `algorithm.yml` records this under `fidelity:`. The tolerances are:

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

## Step 1: shims vs the real toolboxes

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

## Step 2: container vs licensed MATLAB

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

## Deliberate deviations from the authors' code

These are kept in every licensed run, so they don't affect the comparison. The full diff against
the originals is `$FID_WORK/reports/deviations.diff`.

- `calculate_curvature.m`: guards `max(abs(GC(GC<0)))` for the case with no negative
  curvatures, where the original divides by an empty array.
- `vasculature_mask.m` → `vasculature_mask_qsmci.m`:
  - runs `N4BiasFieldCorrection` directly instead of `module load ants/1.9.v4; …`, and falls back
    with a warning if it's missing;
  - doesn't run `mex eig3volume.c` at run time, because it's compiled at build time;
  - doesn't write debug NIfTIs;
  - can return the intermediates as a second output.
- `FrangiFilter3D.m`: a stray `keyboard` is commented out.

## History (v1)

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

## Slurm jobs

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
