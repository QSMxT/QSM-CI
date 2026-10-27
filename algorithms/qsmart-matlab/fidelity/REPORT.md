# qsmart-matlab fidelity report

QSMxT/QSM-CI#295, steps 1–2: does the `qsmart-matlab` container compute what the authors' MATLAB
computes? How to rerun it: [`README.md`](README.md).

- **Checked:** 2026-10-27, on Slurm compute nodes.
- **Licensed MATLAB:** 23.2.0.2459199 (R2023b) Update 5; Image Processing Toolbox 23.2;
  Statistics and Machine Learning Toolbox 23.2.
- **Image:** `ghcr.io/astewartau/qsm-ci/matlab-qsmart@sha256:437824e7fc0511b35c69e0f265ac04601109186efd4d589c09eea1c0416360a5`
  (MATLAB Runtime R2026a), under Apptainer.
- **N4:** every run uses the image's own `N4BiasFieldCorrection` (ANTs 2.5.4), so N4 is not a
  source of difference.
- **Cases:** `sim`, QSM-CI's in-silico head (QSM Challenge 2.0 simulation: 7 T, 4 echoes, 1 mm,
  184×256×128), and `invivo`, one EMTP travelling-head acquisition (3 T, 5 echoes, 164×205×205,
  with a mask that touches the field of view).

## Summary

- **Five shims don't match the toolbox: `imdilate`, `imerode`, `imclose`, `imopen` and
  `imbothat`.** All five are real shim bugs, not harness artefacts, and they change QSMART's
  output: the current image's χ differs from licensed MATLAB by **6.2 % NRMSE in vivo** and
  **1.9 % in silico**. The other six shims pass.
- **The bugs are in how the shims treat the edge of the volume.** IPT treats voxels beyond the
  volume as background for dilation (−Inf, or false) and as foreground for erosion (+Inf). The
  greyscale `imdilate`/`imerode` shims instead wrap round to the opposite face (`circshift`
  with no padding), and the `imclose` shim closes against the edge (no padding). So:
  - `imbothat` (the vessel enhancement in `vasculature_mask`) is wrong near every face of the
    volume; in vivo the vessel mask changes (Dice 0.9934);
  - `imclose` in `QSMART_SDF` and `imdilate` in `calculate_curvature` change when the mask
    touches the FOV (in vivo);
  - `imclose(kernel, [1 1 1])` inside STI Suite's `FastQSM` (the fast initial estimate of
    iLSQR) is wrong on its 7×7×7 kernel in **every** dataset. That is why stage-1 χ differs in
    silico even where the local field is identical.
- **The proposed fix** (a separate commit, not in any image) pads by the structuring element's
  radius with IPT's border value, then crops. With it, all 11 shims are identical to the toolbox
  on every case. Every shim call in the pipeline gives the toolbox's result, apart from the
  Gaussian filters, which differ by at most 1.6e-15. The shim pipeline then matches licensed
  MATLAB to **2.5e-4 % NRMSE in vivo** and **0.018 % in silico**, with identical masks.
- **The MATLAB Runtime itself is not a source of difference.** The container's χ matches licensed
  MATLAB running the same shims to ≤ 1.4e-6 % NRMSE (max |Δ| ≤ 7e-9 ppm).
- **There's no `fidelity:` block in `algorithm.yml` yet.** The pinned image has the shim bugs.
  Rebuild it with the fixed shims, rerun this check, then record the new digest.

## Step 1: shims vs the real toolboxes

`shim_fidelity.m` calls each shim and its toolbox function on the same inputs, in the forms
QSMART, Frangi and STI Suite use them: 3-D volumes, even and odd sizes, masks touching the FOV,
sphere radii 1, 2, 5 and 8, logical and double, and single where the original runs single.

Pass rules:
- identical results for `strel`, `padarray`, morphology and `graythresh`;
- max relative error ≤ 1e-10 for `imfilter`/`imgaussfilt3` (1e-5 on single-precision input);
- ≤ 1e-12 for `prctile`.

Forms that a shim doesn't support and QSMART doesn't use (`strel('disk')`, `padarray`
replicate/symmetric/circular, 3-D `imfilter` kernels, matrix `prctile`) are reported as INFO and
not scored.

| Shim | Current image | Worst error (current) | Cause | Proposed fix |
|---|---|---|---|---|
| `graythresh` | PASS | identical | | PASS |
| `imbothat` | **FAIL** (3/3 cases) | max abs 0.553, in-mask 0.523 | shim bug, via `imclose` | PASS, identical |
| `imclose` | **FAIL** (3/5) | 1 (mask voxels flipped) | shim bug: no border padding, plus the grey wrap-around | PASS, identical |
| `imdilate` | **FAIL** (2/7) | 1 | shim bug: grey path wraps round (`circshift`) | PASS, identical |
| `imerode` | **FAIL** (2/7) | 1 | shim bug: grey path wraps round (`circshift`) | PASS, identical |
| `imfilter` | PASS | rel 2.2e-7 (single input), 1.1e-15 (double) | | PASS |
| `imgaussfilt3` | PASS | rel 1.3e-15 | | PASS |
| `imopen` | **FAIL** (2/4) | 1 | shim bug, via `imdilate`/`imerode` | PASS, identical |
| `padarray` | PASS | identical | | PASS |
| `prctile` | PASS | rel 2.9e-15 | | PASS |
| `strel` | PASS | identical | | PASS |

Logical `imdilate`/`imerode` were already right: binary dilation uses `convn` (zero outside) and
binary erosion is its dual, which matches IPT's rules. The failures are in the greyscale paths
(QSMART calls morphology on double masks and on the magnitude) and in `imclose`.

One harness artefact was fixed along the way. The first harness held `imfilter` on
single-precision input (the original's float32 N4 output) to the double-precision 1e-10
tolerance. It differs by 2e-7 relative, which is single-precision rounding, so single-precision
inputs now use 1e-5.

Failing cases with the current shims:

| Shim | Case | QSMART caller | Max abs | Differing voxels |
|---|---|---|---|---|
| `imdilate` | double mask touching FOV, sphere 5 | calculate_curvature | 1 | 3 / 850593 |
| `imdilate` | random double, sphere 2 | generic greyscale | 0.42 | 18105 / 850593 |
| `imerode` | double mask touching FOV, sphere 1 | calculate_curvature | 1 | 60 / 850593 |
| `imerode` | random double, sphere 2 | generic greyscale | 0.434 | 17843 / 850593 |
| `imclose` | double mask touching FOV, sphere 8 | QSMART_SDF | 1 | 3699 / 850593 |
| `imclose` | logical mask touching FOV, sphere 8 | brainmask.m (generic) | 1 | 3790 / 850593 |
| `imclose` | random double, sphere 2 | generic greyscale | 0.982 | 73962 / 850593 |
| `imopen` | double mask touching FOV, sphere 5 | generic | 1 | 10 / 850593 |
| `imopen` | random double, sphere 2 | generic greyscale | 0.422 | 53603 / 850593 |
| `imbothat` | magnitude, sphere 8, even | vasculature_mask | 0.505 (in-mask 0.016) | 319004 / 860160 |
| `imbothat` | magnitude, brain touching FOV, sphere 8 | vasculature_mask | 0.553 (in-mask 0.523) | 309563 / 850593 |
| `imbothat` | single magnitude (as the original), sphere 8 | vasculature_mask | 0.553 (in-mask 0.523) | 309563 / 850593 |

### Minimal repro

The `shim_*` functions are the shims loaded under other names with `fidelity_shim_copies`, so
they can run next to the toolbox:

```matlab
se = strel('sphere', 1); sse = shim_strel('sphere', 1);
A = zeros(5, 5, 5); A(1, 3, 3) = 1;          % bright voxel on the x = 1 face
D = imdilate(A, se); S = shim_imdilate(A, sse);
[D(5, 3, 3), S(5, 3, 3)]                     % [0 1]: the shim wraps round from x = 1 to x = 5
B = ones(5, 5, 5); B(1, 3, 3) = 0;
D = imerode(B, se);  S = shim_imerode(B, sse);
[D(5, 3, 3), S(5, 3, 3)]                     % [1 0]
M = true(7, 7, 7); M(1, 4, 4) = false;       % a hole on the border face
D = imclose(M, se);  S = shim_imclose(M, sse);
[D(1, 4, 4), S(1, 4, 4)]                     % [0 1]: IPT treats beyond-border voxels as background
```

These gave `[0 1]`, `[1 0]` and `[0 1]` with the current shims, and equal values with the fix.

## Step 2: container vs licensed MATLAB

Each case was run through `recon.m` five ways:

| Run | What |
|---|---|
| `container` | the pinned image under Apptainer, as `qsm_ci/containers.py` runs it (final χ only) |
| `real`, `real2` | licensed MATLAB with the real toolboxes and `shims/` not on the path, run twice |
| `trace` | licensed MATLAB with the current shims; every shim call also runs the toolbox function and logs the difference |
| `trace-fixed` | `trace` with the proposed shim fix |
| `real-single` | `real`, but keeping the vessel mask's N4 output in single precision, as the authors' `vasculature_mask.m` does (informational) |

How to read the tables:
- NRMSE is 100·‖a − b‖/‖b‖ inside the brain mask, where b is the `real` run.
- Max |Δ| is taken over the whole volume.
- Dice is for the vessel set (mask & ~`vasc_only`) and for the R_0 reject set (mask & ~`R_0`).
- χ and fields are in ppm.

### In vivo (`invivo`)

| Output | container vs real | trace vs real (current shims) | trace-fixed vs real | real2 vs real (floor) |
|---|---|---|---|---|
| vessel mask `vasc_only` | – | Dice 0.993425 (10478 voxels) | Dice 1, identical | identical |
| bottom-hat | – | 6.51 %, max 242 | identical | identical |
| vesselness | – | 1.43 %, max 7.8e-4 | 2.3e-12 %, max 5e-16 | identical |
| R_0 | – | identical (no rejects) | identical | identical |
| total field | – | identical | identical | identical |
| stage-1 local field | – | 0.073 %, max 0.0037 | 3.2e-13 %, max 7e-16 | identical |
| stage-1 χ | – | 1.46 %, max 0.031 | 1.6e-4 %, max 8e-7 | identical |
| stage-2 local field | – | 7.04 %, max 0.050 | 3.8e-13 %, max 1e-15 | identical |
| stage-2 χ | – | 7.54 %, max 0.047 | 6.4e-4 %, max 3.8e-6 | identical |
| **final χ** | **6.22 %, max 0.079** | 6.22 %, max 0.079 | **2.5e-4 %, max 3.8e-6** | identical |

Container vs `trace` (the same shims, Runtime vs licensed MATLAB), final χ: 1.4e-6 %, max 6.8e-9.

### In silico (`sim`)

| Output | container vs real | trace vs real (current shims) | trace-fixed vs real | real2 vs real (floor) |
|---|---|---|---|---|
| vessel mask `vasc_only` | – | Dice 1, identical | Dice 1, identical | identical |
| bottom-hat | – | 0 % in mask, max 8.8 (outside the mask) | identical | identical |
| vesselness | – | 3.5e-11 %, max 9e-17 | 3.5e-11 %, max 9e-17 | identical |
| R_0 | – | Dice 1, identical | Dice 1, identical | identical |
| total field | – | identical | identical | identical |
| stage-1 local field | – | 3.4e-13 %, max 4e-16 | 3.4e-13 %, max 4e-16 | identical |
| stage-1 χ | – | 1.72 %, max 0.029 | 1.4e-4 %, max 6e-7 | identical |
| stage-2 local field | – | 5.0e-13 %, max 4e-16 | 5.0e-13 %, max 4e-16 | identical |
| stage-2 χ | – | 3.76 %, max 0.017 | 0.066 %, max 2.7e-4 | identical |
| **final χ** | **1.89 %, max 0.029** | 1.89 %, max 0.029 | **0.018 %, max 2.7e-4** | identical |

Container vs `trace`, final χ: 1.0e-6 %, max 3.5e-9.

In silico, the mask doesn't touch the FOV, so the vessel mask and the local fields already agree.
The 1.9 % comes from `FastQSM`'s `imclose` on its kernel, inside both iLSQR stages.

### Where the differences come from

Every shim call in the pipeline (429 in vivo, 417 in silico), compared with the toolbox on the
same arguments:

| Shim | Call site | Calls (in vivo) | Current shims | Proposed fix |
|---|---|---|---|---|
| `imbothat` | vasculature_mask_qsmci | 1 | max 242 (rel 0.36) | identical |
| `imclose` | QSMART_SDF (sphere 8) | 2 | max 1 in vivo; identical in silico | identical |
| `imdilate` | calculate_curvature (sphere 5) | 2 | max 1 in vivo; identical in silico | identical |
| `imclose` | FastQSM (7×7×7 kernel, `[1 1 1]`) | 2 | max 0.0069 (rel 1), both cases | identical |
| `imerode` | calculate_curvature (sphere 1) | 4 | identical | identical |
| `imfilter` | imgaussian (Frangi) | 36 | ≤ 3.4e-13 abs, 1e-15 rel | same |
| `imgaussfilt3` | sdf_curvature, calculate_curvature | 361 | ≤ 1.6e-15 | same |
| `padarray`, `strel`, `graythresh` | recon, QSM_iLSQR, FastQSM, … | 21 | identical | identical |

With the fix, the remaining 2.5e-4 % (in vivo) to 0.02 % (in silico) is rounding in the Gaussian
filters (≤ 1.6e-15), carried through the iterative iLSQR solver. Licensed MATLAB with the real
toolboxes is bit-for-bit repeatable (`real2`), so there's no run-to-run floor that would hide
this. It's four orders of magnitude below the current error, and below anything a QSM metric
resolves.

### The vessel mask's precision (informational)

The authors' `vasculature_mask.m` uses the N4 output as `load_nii` returns it (single), while
`vasculature_mask_qsmci.m` converts it to double. With the real toolboxes, keeping it single
(`real-single`) changes the final χ by 0.26 % in vivo but by 11.3 % in silico (vessel Dice 0.9931).

The mask is this sensitive because the Otsu threshold on the Frangi vesselness is 0 in both cases
and in every run. The vesselness values are tiny next to `graythresh`'s fixed [0, 1] histogram, so
every voxel with vesselness above 0 becomes a vessel, and rounding decides the edge voxels. The
original behaves the same way, and the shims reproduce it (`graythresh` is identical, with
threshold 0 in every run).

The double conversion predates this check and is outside its scope. Whether to keep it is a
separate decision.

## Deliberate deviations from the authors' code

These are kept in every licensed run, so they don't affect the comparison. The full diff against
the originals is `$FID_WORK/reports/deviations.diff`.

- `calculate_curvature.m`: guards `max(abs(GC(GC<0)))` for when there are no negative curvatures.
  The original divides by an empty array.
- `vasculature_mask.m` → `vasculature_mask_qsmci.m`:
  - runs `N4BiasFieldCorrection` directly instead of `module load ants/1.9.v4; …`, and falls back
    with a warning if it's missing;
  - doesn't run `mex eig3volume.c` at run time (it's compiled at build time);
  - doesn't write debug NIfTIs;
  - converts the N4 output to double (see above);
  - can now return the intermediates as a second output.
- `FrangiFilter3D.m`: a stray `keyboard` is commented out.

## Needs a rebuild

None of the following are in `sha256:437824e7…`: the `recon.m` intermediates option, the second
output of `vasculature_mask_qsmci.m`, and the shim fix. After a rebuild:

1. rerun `submit.sh all`;
2. add the container's intermediates to the comparison;
3. if it passes, record the digest under `fidelity:` in `algorithm.yml`.

## Slurm jobs

| What | Job ids |
|---|---|
| Shims, current / fix | 30713269 / 30713295 |
| Trace runs, current (sim, invivo) | 30713270, 30713272 |
| Trace runs, fix (sim, invivo) | 30713296, 30713298 |
| Container (sim, invivo) | 30711163, 30711169 |
| real, real2, real-single (sim) | 30711164, 30711165, 30711167 |
| real, real2, real-single (invivo) | 30711170, 30711171, 30711173 |
| Compares (sim, invivo) | 30714390, 30714391 |
| Repro | 30714502 |

Wall times: container 4 min 5 s (sim) and 3 min 9 s (invivo), with a peak RSS of 4.2 GB.
Licensed `recon.m`: 238–286 s.
