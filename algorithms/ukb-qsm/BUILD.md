# Building matlab-ukb-qsm (compiled MATLAB → MATLAB Runtime)

The UK Biobank QSM pipeline as a QSM-CI `end-to-end` submission: consumes `phase` (radians),
`magnitude`, `mask` and `params`; produces `chimap` in **ppm**.

Same compile pattern as `../ilsqr-sti/BUILD.md` — bundled NIfTI toolbox, OS gzip, no JVM, STI
Suite v3 obfuscated `.p`, plus an Image Processing Toolbox shim set (the MATLAB Runtime has no
IPT).

## What this reproduces

`ukb/UKBiobank_QSM_core.m` is upstream's `UKBiobank_QSM.m` reconstruction lifted **verbatim**;
`recon.m` is only an adapter that reads the QSM-CI artifacts and calls it. Every divergence from
upstream carries an `% EDIT:` comment, and there are exactly two — N echoes instead of the
hard-coded two, and ppm output (upstream's `x1000` lived in its `niftiwrite` call, which is IO and
outside the lifted region). `ukb/UKBiobank_QSM.m.reference` is the untouched original, so the diff
is auditable.

The chain, from the point where combined phase exists:

| step | function | settings |
|---|---|---|
| phase reliability | `phasevariance_nonlin_v2` | radius 2 mm, per echo |
| mask trim | threshold + `bwareaopen` + `imfill` | 0.6 / 0.5, areas 300 / 50 |
| unwrapping | `MRPhaseUnwrap` (STI Suite, Laplacian) | padsize 64 |
| echo combination | T2*-weighted | `W_i = TE_i·exp(-TE_i/T2*)`, T2* = 40 ms |
| background removal | `V_SHARP` (STI Suite) | `smvsize` 12 |
| mask trim again | as above, tighter | 0.7 / 0.6, areas 200 / 30 |
| inversion | `QSM_iLSQR` (STI Suite) | padsize 64 |

**Not reproduced:** MCPC-3D-S coil combination, which uses FSL PRELUDE to unwrap the Hermitian
inner product. QSM-CI hands this stage already-combined phase, so there is nothing to combine.

**Units:** the original writes `QSM.nii` scaled by 1000, i.e. ppb. The QSM-CI contract is ppm, so
`recon.m` deliberately omits that factor. Echo times are converted from the contract's seconds to
the milliseconds STI Suite and the T2* constant expect.

**Generalisation:** the original is hard-coded for the two echoes UK Biobank acquires. `recon.m`
takes N echoes — the T2* weighting generalises directly, and the two phase-variance thresholds are
applied to the first and last echo, which reduces to the original behaviour when N = 2.

## 1. Fetch build-time deps (not committed; `shims/` and `ukb/` ARE committed)
```bash
cp -r /path/to/NIfTI_20140122                 algorithms/ukb-qsm/nifti
cp -r /path/to/STISuite_V3.0/Core_Functions_P algorithms/ukb-qsm/sti
```
`ukb/phasevariance_nonlin_v2.m` is vendored here under Apache-2.0 with its original header
intact. `ukb/UKBiobank_QSM.m.reference` is the upstream script, kept for provenance and not
compiled.

## 2. Compile
```bash
cd algorithms/ukb-qsm
matlab -batch "addpath('shims'); addpath('nifti'); addpath('sti'); addpath('ukb'); \
  mcc('-m','recon.m','-a','sti','-a','shims','-a','ukb','-o','recon','-d','.')"
```
`-a sti` force-bundles the `.p` files (mcc cannot trace dependencies into pcode). `-a shims` and
`-a ukb` put the IPT replacements and the vendored helper on the deployed path.

## 3. Bake the image and push
```bash
docker build -t ghcr.io/astewartau/qsm-ci/matlab-ukb-qsm:v1 .
docker push  ghcr.io/astewartau/qsm-ci/matlab-ukb-qsm:v1
```
Then make the GHCR package public.

## IPT shims (`shims/`)
Carried over from `ilsqr-sti` (`padarray`, `strel`, `imdilate`, `imerode`, `imclose`, `imopen`),
plus two this pipeline needs and STI Suite does not:

- `bwareaopen` — removes connected components below an area threshold
- `imfill` — the `'holes'` form only, flooding the complement inward from the array border
- `qsmci_label` — the connected-component labelling both are built on (4/8 in 2-D, 6/18/26 in 3-D)

These were exercised in Octave against the cases the pipeline relies on: an isolated speck is
dropped while a large blob survives, the area threshold is respected, an interior 3-D cavity is
filled while a border-connected gap is left open, and 26- versus 6-connectivity separate a
diagonal voxel pair correctly.

## Two things that bite when porting this

**STI Suite needs even matrix dimensions.** UK Biobank's own 256x288x48 is even throughout, so
upstream never meets this; `MRPhaseUnwrap` errors on an odd dimension. `recon.m` zero-pads odd
dimensions before the call and crops back after — lossless for the FFT model, and it keeps the
vendored code untouched.

**`phasevariance_nonlin_v2` assumes UK Biobank's voxel geometry.** It computes a kernel offset as
`(dim - dimX)/2`, which is only an integer for some combinations of matrix size and resolution.
On a 1 mm isotropic phantom it warns ("Integer operands are required for colon operator") on every
call and the reliability kernel may be misplaced. This is upstream's limitation, not the port's,
and it is why `mask_refine` is exposed as a parameter. Reconstructions on non-UKB geometry should
consider `mask_refine: false`.

## Performance

The shims, not STI Suite, dominate if written naively. A per-voxel flood-fill labeller cost
**15.5 s per 2-D slice**; the pipeline calls `bwareaopen` twice per slice over 205 slices in each
of two mask passes, so that alone approached four hours. `qsmci_label` therefore builds its
neighbour edge list with vectorised array shifts and hands it to base MATLAB's `graph`/`conncomp`,
and `imfill` skips labelling entirely in favour of a separable geodesic dilation (a 3x3x3 cube is
separable, so 26-connectivity costs three 1-D dilations, not 26 shifts).

| operation | naive | vectorised | speedup |
|---|---|---|---|
| `bwareaopen`, one 164x205 brain slice | 15.5 s | 0.035 s | 443x |
| `imfill`, 164x205x205 | ~1350 s (est) | 4.1 s | 330x |

Whole pipeline: **531 s** on a 164x205x205x6 phantom, which is then genuinely STI Suite — six
Laplacian unwraps plus V-SHARP plus iLSQR, each on a grid padded by 64 per side.

## Validation

Run in MATLAB R2026a against the QSM-CI in-silico phantom (`ridani-1mm-3t-iso`, 164x205x205,
6 echoes), scored with `eval/qsm_eval.py`'s xSIM on the voxel set every candidate covers (88% of
the dataset mask — UKB's own mask trimming is the binding constraint):

| pipeline | xSIM | NRMSE% | r | scale | sharpness |
|---|---|---|---|---|---|
| ground truth | - | - | - | - | 0.111 |
| **UK Biobank (this submission)** | 0.495 | 60.8 | 0.808 | 0.568 | 0.122 |
| QSMxT v8.3.2 two-pass | 0.415 | 70.4 | 0.724 | 0.480 | 0.122 |
| QSM.rs iSMV + WH-QSM | 0.462 | 62.2 | 0.796 | 0.591 | 0.086 |

Sharpness is mean |gradient| over dynamic range, inside the mask. The shims were checked
separately in Octave and MATLAB: area threshold respected, isolated speck dropped while a large
blob survives, interior 3-D cavity filled while a border-connected gap stays open, and 26- versus
6-connectivity separating a diagonal voxel pair.
