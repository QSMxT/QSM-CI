# Building matlab-ukb-qsm (compiled MATLAB → MATLAB Runtime)

The UK Biobank QSM pipeline as a QSM-CI `end-to-end` submission: consumes `phase` (radians),
`magnitude`, `mask` and `params`; produces `chimap` in **ppm**.

Same compile pattern as `../ilsqr-sti/BUILD.md` — bundled NIfTI toolbox, OS gzip, no JVM, STI
Suite v3 `.p` code, compiled with **licensed MATLAB R2023b against the real Image Processing
Toolbox** (no shims) and baked onto the R2023b MATLAB Runtime, the release the fidelity check
([`../../fidelity/matlab/`](../../fidelity/matlab/README.md)) runs on.

## What this reproduces

`ukb/UKBiobank_QSM_core.m` is upstream's `UKBiobank_QSM.m` reconstruction lifted **verbatim**;
`recon.m` is only an adapter that reads the QSM-CI artifacts and calls it. Every difference from
upstream is listed in [README.md](README.md) ("Exactly what differs from the original"); the two
code edits carry an `% EDIT:` comment — N echoes instead of the hard-coded two (in the lifted code)
and even-dimension padding (in the adapter) — and `recon.m` masks the phase as upstream's is
before it calls the lifted code (since v3). `ukb/UKBiobank_QSM.m.reference` is the untouched
original, so the diff is auditable. A third output copies intermediates out for the fidelity check (lines marked
`% EDIT (intermediates)`); it changes no computation.

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

## 1. Fetch build-time deps (not committed; `ukb/` IS committed)
```bash
cp -r /path/to/NIfTI_20140122                 algorithms/ukb-qsm/nifti
cp -r /path/to/STISuite_V3.0/Core_Functions_P algorithms/ukb-qsm/sti
```
`ukb/phasevariance_nonlin_v2.m` is vendored here under Apache-2.0 with its original header
intact. `ukb/UKBiobank_QSM.m.reference` is the upstream script, kept for provenance and not
compiled. [`fidelity/config.sh`](fidelity/config.sh) (`fid_assemble`) is the same recipe as a script.

## 2. Compile
```bash
cd algorithms/ukb-qsm
matlab -batch "addpath('nifti'); addpath('sti'); addpath('ukb'); \
  mcc('-m','recon.m','-a','sti','-a','ukb','-o','recon','-d','.')"
```
`-a sti` force-bundles the `.p` files (mcc cannot trace dependencies into pcode); `-a ukb` puts the
vendored helper on the deployed path. The UKB code's own `bwareaopen` and `imfill` calls are traced;
the Image Processing Toolbox functions STI Suite's pcode calls (`imclose`, `imdilate`, `imerode`,
`padarray`, `strel`) are named in `recon.m`'s `%#function` pragma, found by profiling a licensed run
(`fidelity/matlab/submit.sh ukb-qsm trace`). Check that `unresolvedSymbols.txt` and
`mccExcludedFiles.log` list nothing. The harness does this compile as a Slurm job
(`submit.sh ukb-qsm build`; log in `reports/build.txt`).

## 3. Bake the image and push
```bash
podman build -t ghcr.io/astewartau/qsm-ci/matlab-ukb-qsm:v3 .   # needs ./recon from §2
podman push  ghcr.io/astewartau/qsm-ci/matlab-ukb-qsm:v3
```
Keep the package public, pin `image:` in `algorithm.yml` by the pushed digest, and rerun the
fidelity check ([`fidelity/REPORT.md`](fidelity/REPORT.md)).

Images: `v1` (R2026a Runtime, IPT shims including our own `bwareaopen`/`imfill`/`qsmci_label`, whose
greyscale `imdilate`/`imerode` wrapped round at the volume border); `v2` (R2023b, the real toolboxes,
no shims); `v3` (as v2, with the phase masked before unwrapping as upstream's is; see `fidelity:`
in `algorithm.yml`).

## Two things that bite when porting this

**STI Suite needs even matrix dimensions.** UK Biobank's own 256x288x48 is even throughout, so
upstream never meets this; `MRPhaseUnwrap` errors on an odd dimension. `recon.m` zero-pads odd
dimensions before the call and crops back after — lossless for the FFT model, and it keeps the
vendored code untouched.

**`phasevariance_nonlin_v2` assumes UK Biobank's voxel geometry.** It places its kernel at
`(dim - dimX)/2 + 1`, a half-integer on many grids (1 mm isotropic among them). MATLAB warns
("Integer operands are required for colon operator when used as index") on every call and rounds
the index up (measured against this image by QSM.rs's port, `utils::phase_reliability`), so the
kernel sits half a voxel off centre there. This is upstream's code, kept as it is.

## Performance

The v1 image ran our own `bwareaopen`/`imfill` shims, vectorised to keep the per-slice calls fast.
v2 runs the real Image Processing Toolbox functions instead.

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

Sharpness is mean |gradient| over dynamic range, inside the mask. These scores are from the v1
image (R2026a, shims).
