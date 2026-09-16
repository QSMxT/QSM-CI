# Building matlab-ukb-qsm (compiled MATLAB → MATLAB Runtime)

The UK Biobank QSM pipeline as a QSM-CI `end-to-end` submission: consumes `phase` (radians),
`magnitude`, `mask` and `params`; produces `chimap` in **ppm**.

Same compile pattern as `../ilsqr-sti/BUILD.md` — bundled NIfTI toolbox, OS gzip, no JVM, STI
Suite v3 obfuscated `.p`, plus an Image Processing Toolbox shim set (the MATLAB Runtime has no
IPT).

## What this reproduces

`UKBiobank_QSM.m` from the Oxford pipeline, from the point where combined phase exists:

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

## Validation status

Not yet scored against ground truth. The MATLAB-only path (`MRPhaseUnwrap`, `V_SHARP`,
`QSM_iLSQR`) cannot run under Octave because STI Suite ships obfuscated pcode, so the end-to-end
check needs a MATLAB licence. What has been checked without one: `recon.m` and
`phasevariance_nonlin_v2.m` parse, the reliability map runs on real phantom geometry, and the
mask-cleanup sequence behaves as described above. **Score it on `data/sim` before publishing.**
