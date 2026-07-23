# INR-QSM

Subject-specific **unsupervised** deep-learning **dipole inversion** using an **implicit neural
representation** (a coordinate MLP optimized per subject — no pretrained recon weights).

> **STATUS: scaffold — needs image build + push (human).** The container image
> `ghcr.io/astewartau/qsm-ci/inr-qsm:v1` has not been built or pushed yet, and this scaffold has not
> been run end-to-end. See `BUILD.md` and the checklist below.

- **Stage:** `dipole` (localfield → chimap, ppm)
- **Engine:** [INR-QSM](https://github.com/AMRI-Lab/INR-QSM) — PyTorch SIREN coordinate MLP,
  per-subject optimization. **CPU by default** here (reference is GPU-oriented — see RUNTIME/GPU
  CAVEAT).
- **Reference:** Zhang M., Feng R., Li Z., Feng J., Wu Q., Zhang Z., Ma C., Wu J., Yan F., Liu C.,
  Zhang Y., Wei H. *A subject-specific unsupervised deep learning method for quantitative
  susceptibility mapping using implicit neural representation.* Medical Image Analysis 95:103173,
  2024. DOI: [10.1016/j.media.2024.103173](https://doi.org/10.1016/j.media.2024.103173)

## What it does

INR-QSM represents the susceptibility map as a **continuous function of spatial coordinates**,
χ(x) = MLP(x), parameterized by a **SIREN** (sine-activated MLP). It loads **no trained recon
weights**; for each input volume it **optimizes** the MLP so that χ, convolved with the QSM dipole
kernel, reproduces the input local field, regularized by an **edge-weighted TV** term and a
**gradient-domain** data-consistency term. This makes it subject-specific and free of the
generalization concerns of pretrained networks — at the cost of per-volume runtime. An **optional**
transfer-learning weight init (shipped in the repo) is used only to **accelerate** convergence; it is
not a trained reconstruction model.

## Why `dipole`

INR-QSM maps a **local (tissue) field** to **susceptibility** through the dipole kernel — purely a
dipole inversion (no field-mapping / background-field removal). So it consumes `localfield` and
produces `chimap`: the `dipole` stage. (The repo's `main.py` loads `phi` = tissue field and the
`data_prep` demo says "the tissue phase ... should be normalized with a unit of ppm".)

## Units & kernel

- **Input/output units.** QSM-CI `localfield` is the local/tissue field already in **ppm**, exactly
  the repo's `phi`. Fed unchanged. Output susceptibility is **ppm**, written on the input affine.
- **Dipole kernel.** Built by the repo's `utils.calc_d2_matrix1` from the **B0 direction** and
  **voxel size**: the k-space kernel `D = 1/3 − (k·B̂0)²/|k|²` (DC set to 0). B0 direction from
  `params.json` / `QSMCI_B0_DIR`; voxel size from the NIfTI header (fallback `params.json` /
  `QSMCI_VOXEL_SIZE`). The centered orthonormal FFTs are the repo's `myfftnc`/`myifftnc`.

## Implementation notes & deliberate deviations from the reference

This wrapper **reuses the reference network and operators verbatim** (`model.siren_model`,
`utils.calc_d2_matrix1`, `utils.build_coordinate_train`, `utils.myfftnc/myifftnc`, `utils.TVLoss`,
`utils.GradientLoss`). It **deviates** from the reference `main.py` in three documented ways so it
runs robustly on CPU inside CI:

1. **Full-volume optimization, not the patch-based non-local phase-compensation loop.** The reference
   tiles the volume into 96×96×48 patches and runs an iterative "phase compensation" to model the
   non-local field from neighboring patches. Here χ is a **single MLP over the whole volume**, so the
   forward model `F⁻¹(D·F·χ)` is exact and non-local by construction — no patch stitching /
   compensation. This optimizes the **same** data-consistency objective but is **not byte-identical**
   to the paper's patch pipeline and may differ near boundaries. (This is the biggest fidelity
   caveat; a future version could port the patch/compensation loop for a GPU runner.)
2. **No CUDA AMP / float16.** The reference uses `torch.cuda.amp` autocast + `GradScaler` + fp16
   (CUDA-only). We run **float32** on CPU (same math, CPU-safe).
3. **WG (edge-weight matrix) computed in Python.** The reference builds WG from a **MATLAB STISuite**
   FastQSM/STAR-QSM initial recon (`data_prep/TVweighting.m`). STISuite is proprietary MATLAB and is
   **not shipped**. We reimplement `TVweighting.m` in Python (`_tv_weighting`) on an **in-house TKD**
   initial χ estimate. This **approximates**, and does not reproduce, the STISuite-based WG.

## How QSM-CI runs it

```bash
bash run.sh                       # -> python inr_qsm_infer.py /input /output
```

## Parameters (`algorithm.yml`)

| Parameter | Default | Meaning |
|-----------|---------|---------|
| `epoch` | 50 | Per-subject optimization epochs. Main runtime/quality knob. |
| `star_lr` | 1e-5 | Starting Adam learning rate. |
| `end_lr` | 2e-7 (0.02e-5) | Final LR (exponential schedule). |
| `hidden_dim_num` | 512 | SIREN width. |
| `num_layers` | 10 | SIREN depth. |
| `TV_weight` | 0.15 | Edge-weighted TV regularizer weight. |
| `gd_weight` | 1.0 | Gradient-domain data-consistency weight. |

All are legitimate reference **defaults** (from `config.py`), not tuned values. Overrides arrive via
`/input/config.json` or `QSMCI_SET_*`. Note the shipped transfer-learning init only matches the
**default** width/depth; changing `hidden_dim_num`/`num_layers` skips it (random init) — controlled by
`INR_QSM_USE_TL`.

## RUNTIME / GPU CAVEAT  ⚠️

Like all untrained per-subject methods, INR-QSM **trains a network on every input volume**. The
reference was tested on an **NVIDIA A6000 (~10 GB VRAM)** and uses CUDA AMP. Consequences for QSM-CI:

- **On CPU (the default here), optimization may be slow and can exceed the CI time limit (default 2 h
  → DNF).** This has **not** been timed on the CI phantom yet.
- Full-volume 3D FFTs each epoch plus a wide/deep SIREN are memory- and compute-heavy on CPU.
- Mitigations the human should consider: **(a)** provide a **GPU runner** (drop
  `CUDA_VISIBLE_DEVICES=-1`, build a CUDA torch wheel — and note AMP/fp16 was dropped here, so a GPU
  run is float32 and heavier than the paper's); or **(b)** cap cost by lowering `epoch`, `num_layers`
  and/or `hidden_dim_num`.

## Assumptions to verify

1. **localfield is in ppm** (per `CONTRACT.md` and the repo's `phi`) — no unit rescale.
2. **WG approximation.** The Python TKD-seeded WG is a stand-in for STISuite FastQSM+TVweighting.
   Verify it behaves sensibly (edges down-weighted); consider tuning the `(0.5, 0.7)` percentile
   range and TKD threshold if results look over/under-smoothed.
3. **Full-volume vs. patch pipeline.** The non-local phase-compensation patch loop is not replicated;
   confirm this is acceptable, or plan to port it for a GPU runner.
4. **B0 direction / voxel size** from `params.json` / header — verify against the challenge geometry.
5. **Coordinate/affine convention.** The repo's `build_coordinate_train` uses a `[-1,1]` normalized,
   voxel-anisotropy-scaled grid; we write on the input NIfTI affine (orientation preserved). Confirm
   no axis flip is needed relative to the reference's identity-diagonal affine.
6. **Referencing.** Output is masked; QSM is defined up to a constant — confirm the scorer's
   detrend/reference handling is satisfied (no explicit demeaning is applied here).
7. **CPU feasibility / timeout** — untested; see RUNTIME/GPU CAVEAT.

## Human checklist to finish

- [ ] Build & push the image (see `BUILD.md`; pin `INR_QSM_REF` to a commit SHA).
- [ ] Run once locally on a `qsm-forward` phantom to confirm plumbing + units + scale + sign.
- [ ] **Time a CPU run** and decide: GPU runner vs. lower `epoch`/`num_layers`/`hidden_dim_num`.
- [ ] Decide whether the WG approximation and full-volume (non-patch) objective are acceptable, or
      port the patch/phase-compensation pipeline for a GPU variant.

_Citations/DOIs are best-effort and should be verified._
