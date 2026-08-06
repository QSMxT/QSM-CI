# AFTER-QSM (`after-qsm`) — dipole inversion

**AFTER-QSM** (Affine Transformation Edited and Refined deep neural network) is a pretrained,
**affine-equivariant** deep network for QSM **dipole inversion** — mapping a local (tissue) field to
susceptibility. Unlike axial-trained networks (xQSM, QSMnet, …), it is robust to **arbitrary head
orientation** and **anisotropic resolution** down to 0.6 mm isotropic.

- **Stage:** `dipole` — consumes `localfield` (ppm) + `params`, produces `chimap.nii.gz` (χ, ppm).
- **Reference:** Xiong Z., Gao Y., Liu F., Sun H. *Affine transformation edited and refined deep neural
  network for quantitative susceptibility mapping.* **NeuroImage** 2022.
  [doi:10.1016/j.neuroimage.2022.119655](https://doi.org/10.1016/j.neuroimage.2022.119655)
  (arXiv: [2211.13942](https://arxiv.org/abs/2211.13942)).
- **Code:** <https://github.com/sunhongfu/AFTER-QSM> (this is the standalone repo; the
  `sunhongfu/deepMRI/AFTER-QSM` subdir redirects here).

## How it works

Two stages, both pretrained (one checkpoint, `checkpoints/AFTER-QSM.pkl`):

1. **Coarse inversion.** The input field is **affine-transformed** into the network's canonical frame
   (axial orientation, 0.6 mm isotropic) using the supplied **voxel size** and **B0 direction**
   (z-projections). A U-net does the dipole inversion, then the result is **inverse-affine-transformed**
   back to the acquisition frame. Because the inversion always happens in a fixed canonical geometry,
   the network generalizes across orientation and resolution.
2. **Refinement (deblur).** A Residual-Dense refinement network deblurs the coarse map and corrects the
   susceptibility underestimation introduced by the affine resampling. This is what the paper's ablation
   shows is essential for image quality.

AFTER-QSM produces two maps — a coarse (**blur**) and a refined (**deblur**) susceptibility map. This
submission publishes the **refined (deblur)** map as the canonical `chimap.nii.gz`.

## Units

The QSM-CI `localfield` is the tissue field already in **ppm** (normalized by B0). AFTER-QSM is trained
(see the repo's `utils/dataset.py`) on χ maps in ppm forward-projected through the **unnormalized**
dipole kernel `D = 1/3 − kz²/k²`, i.e. the field it expects is in the **same units as χ = ppm**. So the
ppm local field is fed **straight through with no rescaling**, and the output susceptibility (ppm) is
written unchanged. `inference.run_after_qsm` reads the input NIfTI affine and writes it back onto the
output, so `chimap.nii.gz` lands on the input grid.

## Voxel size + B0 direction

AFTER-QSM's affine stage **requires** the true acquisition geometry. The wrapper forwards it from
`params` via the QSM-CI environment variables (see [CONTRACT.md](../../CONTRACT.md)):

| AFTER-QSM arg | Source env var | Meaning |
|---------------|----------------|---------|
| `--voxel-size X Y Z` | `QSMCI_VOXEL_SIZE` | voxel size in mm |
| `--b0-dir X Y Z`     | `QSMCI_B0_DIR`     | B0 direction unit vector (z-projections) |

Defaults fall back to `1 1 1` / `0 0 1` (axial) if unset. **`mask` is not consumed** — AFTER-QSM
derives its own brain mask from the nonzero voxels of the input field — which is why `algorithm.yml`
declares `inputs: [localfield, params]`.

## Parameters

| Name | Default | Meaning |
|------|---------|---------|
| `segment_num` | `3` | Refinement-stage slab count (memory/quality knob). Larger = less peak VRAM; the reference suggests `8` for <12 GB and `4` for <24 GB. |

Override with `qsm-ci run after-qsm --set segment_num=8` (written to `/input/config.json` and exposed
as `QSMCI_SET_SEGMENT_NUM`).

## RUNTIME / GPU CAVEAT — why this submission is `ci_skip`ed

AFTER-QSM runs **two 3-D CNNs** plus **full-volume 3-D affine grid resampling**; the reference
recommends an **8 GB+ VRAM NVIDIA GPU**. QSM-CI has **no GPU runner yet**, and on CPU this pipeline does
not fit the hosted time budget. The submission therefore sets:

```yaml
runner: gpu
ci_skip: true
```

`ci_skip: true` keeps the submission fully in the repo (reviewable code, committed weights, provenance)
but tells the scorer **not to run it**: `discover_algorithms()` in `scripts/pipeline.py` skips it in
every mode and `scripts/ci_eval_targets.py` drops it from the PR smoke matrix, so it never DNFs a
runner. It is present-but-unscored (absent from the leaderboard). **Un-skip** (set `false` / remove)
once a GPU runner exists and a GPU route is added to `score.yml`, then let CI score it.

The Docker image is **GPU-capable, CPU-optional**: the default CUDA PyTorch wheel also runs on CPU-only
hosts (torch falls back when no GPU is visible). The device is chosen **at run time** inside
`inference.run_after_qsm` (`cuda:0` if available, else `cpu`); `QSMCI_FORCE_CPU=1` forces CPU.

## Checkpoint provenance

`checkpoints/AFTER-QSM.pkl` (~34 MB) is a torch `state_dict` — `{recon_model_state,
refine_model_state}` — **committed directly** in the AFTER-QSM repo (a real zip/pickle, not a git-LFS
pointer, not a Release asset). It is baked into the image simply by cloning the repo at build time (no
separate download), so the run phase is fully offline (`--network none`).

## License

The AFTER-QSM repo ships **no LICENSE file** (confirmed). Treat as **academic use; cite the paper**. The
code and checkpoint are cloned/baked at build time.

## Files

| File | Role |
|------|------|
| `algorithm.yml` | Manifest: stage `dipole`, image, `run: bash run.sh`, `runner: gpu`, `ci_skip: true`, `parameters` (`segment_num`). |
| `Dockerfile` | CUDA-capable (CPU-optional) PyTorch base + `git clone` AFTER-QSM to `/opt/AFTER-QSM` (committed checkpoint comes along). Code is mounted, not COPYed. |
| `run.sh` | Wires `--voxel-size`/`--b0-dir`/`--segment-num` from env, drives the repo's `run.py`, publishes the refined (deblur) map as `chimap.nii.gz`. |
| `BUILD.md` | Exact build/push + smoke-test commands (deferred to a GPU host). |
