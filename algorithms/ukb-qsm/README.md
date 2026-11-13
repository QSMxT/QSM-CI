# UK Biobank QSM pipeline

The susceptibility pipeline UK Biobank runs on its swMRI data, submitted so the reference behind
the UK Biobank susceptibility IDPs can be scored on the same benchmark as everything else.

**Upstream:** <https://git.fmrib.ox.ac.uk/cwang/uk_biobank_qsm_pipeline> (FMRIB GitLab, Apache-2.0),
part of the UK Biobank brain imaging pipeline at
<https://git.fmrib.ox.ac.uk/falmagro/uk_biobank_pipeline_v_1.5>.

**Citation:** Wang et al., *Phenotypic and genetic associations of quantitative magnetic
susceptibility in UK Biobank brain imaging*, Nature Neuroscience 2022.
[doi:10.1038/s41593-022-01074-w](https://doi.org/10.1038/s41593-022-01074-w)

**Authors of the reconstruction code:** Chaoyue Wang, Benjamin C. Tendler, Karla L. Miller.
The upstream repository additionally credits Fidel Alfaro-Almagro, Alberto Llera and
Stephen M. Smith as contributors to the wider pipeline.

## Exactly what differs from the original

`ukb/UKBiobank_QSM_core.m` is upstream's `UKBiobank_QSM.m` reconstruction lifted **verbatim**.
`recon.m` is only an adapter: it reads the QSM-CI artifacts, calls that function, writes the
result. The untouched original is kept at `ukb/UKBiobank_QSM.m.reference` so the diff can be
checked directly.

Every difference is listed below (audited against upstream line by line, 2026-11-13). Two are
code edits, each marked `% EDIT:` in the source. The rest are inputs that QSM-CI's contract supplies
in place of what upstream reads from DICOM and from UK Biobank's structural pipeline, or upstream
code (IO, coil combination) that is not carried over. A third output that copies intermediates out
for QSM-CI's fidelity check, marked `% EDIT (intermediates)`, changes no computation.

### 1. Multi-echo — *code edit*, in the lifted code

Upstream is hard-coded for the two echoes UK Biobank acquires: `phase1`, `phase2`, `uwphase1`,
`uwphase2`, `W1`, `W2`. Here the unwrap and the weighting loop over N echoes. **At N = 2 the
arithmetic is identical to upstream** — the weights `W_i = TE_i·exp(-TE_i/T2*)` and the effective
TE reduce exactly. The phase-variance maps, which upstream computes from `phase1` and `phase2`,
are computed from the first and last echo.

### 2. Output units — *absence*

Upstream ends with `niftiwrite(single(qsm_iLSQR_vsf * 1000), ...)`, i.e. **parts per billion**.
The QSM-CI artifact contract is **ppm**, so that factor is not applied. The `×1000` lived in the
`niftiwrite` call, which is IO and sits outside the lifted region, so nothing was edited to
achieve this — it simply is not carried over.

### 3. Coil combination — *absence*

Upstream begins by reading DICOM and combining coils with MCPC-3D-S, using FSL PRELUDE to unwrap
the Hermitian inner product. QSM-CI supplies already-combined phase, so that whole stage is
upstream of this submission and absent here. **Note this means the Laplacian `MRPhaseUnwrap`, not
PRELUDE, is the unwrapping step being benchmarked** — PRELUDE only ever touched the inner product
during coil combination.

Upstream's combined phase is zeroed outside its brain mask before anything reads it
(`phase1 = mask .* angle(combined1)`, l. 158-160), so `MRPhaseUnwrap` solves on the masked phase.
`recon.m` masks QSM-CI's phase the same way before calling the lifted code. **Images up to v2 did
not**: they unwrapped the raw phase over the whole volume, which differs from upstream (fixed in
v3, decision 148).

### 4. Even-dimension padding — *code edit*, in the adapter

STI Suite indexes assuming even matrix dimensions. UK Biobank's own 256×288×48 is even on every
axis, so upstream never encounters this, but `MRPhaseUnwrap` errors on an odd dimension. The
adapter zero-pads odd dimensions before the call and crops back after, which is lossless for the
FFT model and leaves the vendored code untouched. (The phase-variance maps are computed on the
padded grid, so on an odd grid they are not what upstream's code would make of the unpadded one.)

### 5. Brain mask — *input*

Upstream's mask is UK Biobank's structural brain mask (from the T1 pipeline, registered to the
SWI), binarised with `fslmaths -thr 0.6 -bin`. That needs the T1 and UK Biobank's structural
pipeline; here the dataset's `mask.nii.gz` stands in for it. Everything after (both trims) is
upstream's.

### 6. Field strength — *input*

Upstream passes `QSM_iLSQR` the DICOM's nominal `MagneticFieldStrength` (e.g. 3). Here it is
`params.json` `B0`, which for in vivo datasets is computed from the scanner's centre frequency
(`ImagingFrequency` / γ; CONTRACT.md), as QSMxT uses for every run (orchestrator decisions 31 and
149). On a Siemens Prisma (2.89 T) χ scales by about 3.6 % against the nominal 3 T. The nominal
value is `params.json` `B0_nominal` where a dataset has it.

### 7. Geometry — *input*

Upstream computes the field direction from `ImageOrientationPatient` (`H = [-Xz, -Yz, Zz]`, for
its own array orientation) and the voxel size from `PixelSpacing` and `SliceThickness`; here they
are `params.json` `B0_dir` and `voxel_size`, in the image's own axes. Both describe the same
geometry. The mask is logical here and `double` upstream (read from NIfTI); every function it
reaches gives the same result for either.

## A caveat on generalisation

`phasevariance_nonlin_v2` assumes UK Biobank's voxel geometry. It places its kernel at
`(dim − dimX)/2 + 1`, a half-integer for many combinations of matrix size and resolution (1 mm
isotropic among them). MATLAB then warns ("Integer operands are required for colon operator when
used as index") on every call and rounds the index up, so the reliability kernel sits half a
voxel off centre on those grids. This is upstream's code, followed as it is. (Earlier versions of
this README offered a `mask_refine` switch to turn the trimming off; `recon.m` never read one, and
the trimming always runs.)

Because the default trimming is faithful to what UK Biobank actually runs, scored coverage is
smaller than other submissions': on the in-silico phantom it reconstructs 88% of the dataset mask.

## Scores

Measured on `ridani-1mm-3t-iso` (164×205×205, 6 echoes), on the voxel set every candidate covers:

| pipeline | xSIM | NRMSE% | r | scale | sharpness |
|---|---|---|---|---|---|
| ground truth | — | — | — | — | 0.111 |
| **UK Biobank (this submission)** | 0.495 | 60.8 | 0.808 | 0.568 | 0.122 |
| QSMxT v8.3.2 two-pass | 0.415 | 70.4 | 0.724 | 0.480 | 0.122 |
| QSM.rs iSMV + WH-QSM | 0.462 | 62.2 | 0.796 | 0.591 | 0.086 |

Sharpness is mean |gradient| over dynamic range inside the mask. See `BUILD.md` for how to
compile and for the performance notes.
