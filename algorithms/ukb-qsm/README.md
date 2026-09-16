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

There are four differences in total. Two are actual code edits, each marked `% EDIT:` in the
source; the other two are absences, where upstream code simply is not carried over and so there
is nothing to mark.

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

### 4. Even-dimension padding — *code edit*, in the adapter

STI Suite indexes assuming even matrix dimensions. UK Biobank's own 256×288×48 is even on every
axis, so upstream never encounters this, but `MRPhaseUnwrap` errors on an odd dimension. The
adapter zero-pads odd dimensions before the call and crops back after, which is lossless for the
FFT model and leaves the vendored code untouched.

## A caveat on generalisation

`phasevariance_nonlin_v2` assumes UK Biobank's voxel geometry. It computes a kernel offset as
`(dim − dimX)/2`, an integer only for some combinations of matrix size and resolution. On a 1 mm
isotropic phantom it warns on every call and the reliability kernel may be misplaced. This is
upstream's limitation, not the port's, and it is why `mask_refine` is exposed as a parameter —
set it false to reconstruct across the mask the dataset supplies.

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
