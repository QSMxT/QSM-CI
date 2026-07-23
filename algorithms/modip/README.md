# MoDIP

Model-based **deep image prior** for QSM **dipole inversion** — an **unsupervised / untrained**
deep-learning method that optimizes a network **per subject** at inference time (no pretrained
weights).

> **STATUS: scaffold — needs image build + push (human).** The container image
> `ghcr.io/astewartau/qsm-ci/modip:v1` has not been built or pushed yet, and this scaffold has not
> been run end-to-end. See `BUILD.md` and the checklist below.

- **Stage:** `dipole` (localfield → chimap, ppm)
- **Engine:** [MoDIP](https://github.com/sunhongfu/MoDIP) — PyTorch, per-subject deep-image-prior
  optimization. **CPU by default** here (reference is GPU-oriented — see RUNTIME/GPU CAVEAT).
- **Reference:** Xiong Z., Gao Y., Liu Y., Fazlollahi A., Nestor P., Liu F., Sun H. *Quantitative
  susceptibility mapping through model-based deep image prior (MoDIP).* NeuroImage 291:120583, 2024.
  DOI: [10.1016/j.neuroimage.2024.120583](https://doi.org/10.1016/j.neuroimage.2024.120583)
  (Note: the DOI in the submission brief, …120540, did not resolve to this paper; the verified DOI is
  …120583.)
- **Also mirrored in:** `sunhongfu/deepMRI/MoDIP`.

## What it does

MoDIP wraps a small 3D U-Net (a *deep image prior*) inside the QSM **dipole forward model**. It loads
**no trained weights**; instead, for each input volume it **optimizes** the network so that the
susceptibility it predicts, convolved with the dipole kernel, reproduces the input local field. A
gradient-domain (Laplacian/Sobel) term regularizes the fit. After `epoch_num` iterations the final
susceptibility is de-meaned over the foreground and written out. This makes it **subject-specific**
and free of the generalization concerns of pretrained networks — at the cost of per-volume runtime.

## Why `dipole`

MoDIP maps a **local (tissue) field** directly to **susceptibility** using the dipole kernel — it is
purely a dipole inversion (no field-mapping or background-field removal). So it consumes `localfield`
and produces `chimap`: the `dipole` stage. The repo's `run.py --input_type phi` and
`inference.run_modip(lfs_nii_path=...)` take exactly the local field map.

## Units & kernel

- **Input/output units.** QSM-CI `localfield` is the local/tissue field already in **ppm** (per
  `CONTRACT.md`), which is MoDIP's expected local-field input; fed unchanged. Output susceptibility
  is **ppm**, written unchanged on the input affine.
- **Dipole kernel.** Built internally by the repo's `utils.handy.generate_dipole` from the **B0
  direction** (`z_prjs`) and **voxel size** (`vox`) — the standard k-space kernel
  `1/3 − (k·B̂0)²/|k|²`. We pass B0 direction from `params.json` / `QSMCI_B0_DIR` and voxel size from
  the NIfTI header (falling back to `params.json` / `QSMCI_VOXEL_SIZE`).

## How QSM-CI runs it

```bash
bash run.sh                       # -> python modip_infer.py /input /output
```

`modip_infer.py` calls the repo's `inference.run_modip` (its own optimization loop), then intersects
the output with the QSM-CI brain mask and writes `chimap.nii.gz` on the input affine.

## Parameters (`algorithm.yml`)

| Parameter | Default | Meaning |
|-----------|---------|---------|
| `epoch_num` | 500 | Per-subject optimization iterations (reference default). Main runtime/quality knob. |
| `lr` | 5e-4 | Adam learning rate (reference default). |
| `base` | 32 | DIP U-Net base channel count (reference default). Lower = less memory/compute. |

These are legitimate reference **defaults** (not tuned values). Overrides arrive via
`/input/config.json` or `QSMCI_SET_*` and fall back to these defaults.

## RUNTIME / GPU CAVEAT  ⚠️

This is the key benchmark-fit risk. Unlike a pretrained network (one forward pass), MoDIP **trains a
network on every input volume** — the reference default is **500 optimization iterations** over the
whole 3D volume, each iteration doing FFT-based dipole convolutions and a full U-Net forward/backward
pass. The reference targets an **NVIDIA GPU**. Consequences for QSM-CI:

- **On CPU (the default here), a full 500-iteration run may be very slow and can exceed the CI time
  limit (default 2 h wall-clock → DNF).** This has **not** been timed on the CI phantom yet.
- Mitigations the human should consider: **(a)** provide a **GPU runner** (drop
  `CUDA_VISIBLE_DEVICES=-1`, build a CUDA torch wheel); or **(b)** cap iterations by lowering
  `epoch_num` (e.g. 100–200) — the reference README explicitly supports fewer iterations, and ships
  `result100.nii`/`result200.nii`/`result500.nii` as examples of the quality/iteration trade-off;
  and/or lower `base` to reduce memory/compute.

## Assumptions to verify

1. **localfield is in ppm** (per `CONTRACT.md`) — no unit rescale applied.
2. **Mask.** MoDIP derives its own foreground as `(localfield != 0)`; we additionally intersect the
   result with the provided QSM-CI `mask.nii.gz`. Confirm the local field's zero-background matches
   the mask closely enough (MoDIP crops the nonzero bounding box for memory).
3. **B0 direction** taken from `params.json` / `QSMCI_B0_DIR` (default `[0,0,1]`); **voxel size**
   from the NIfTI header. Verify these agree with the challenge data's true acquisition geometry.
4. **De-meaning.** MoDIP subtracts the foreground mean from the output (QSM is defined up to a
   constant). QSM-CI's scorer detrends/compares accordingly, but confirm no additional referencing
   is expected.
5. **CPU feasibility / timeout** — untested; see RUNTIME/GPU CAVEAT.

## Human checklist to finish

- [ ] Build & push the image: `docker build -t ghcr.io/astewartau/qsm-ci/modip:v1 algorithms/modip && docker push ...` (pin `MODIP_REF` to a commit SHA for reproducibility).
- [ ] Run once locally on a `qsm-forward` phantom (`qsm-ci run modip --localfield lf.nii.gz --mask mask.nii.gz --params params.json --truth chi.nii.gz`) to confirm plumbing + units + scale.
- [ ] **Time a CPU run** and decide: GPU runner vs. lower `epoch_num` (iteration cap) to fit the CI time limit.
- [ ] Verify output scale/sign against a known-good QSM (de-meaning + ppm).

_Citations/DOIs are best-effort and should be verified._
