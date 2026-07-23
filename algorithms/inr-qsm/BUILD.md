# BUILD — INR-QSM (`inr-qsm`)

This submission is a **scaffold**. The container image is **not** built or pushed, and the pipeline
has **not** been run. This file lists exactly what a human must do to finish.

## 1. Build & push the environment image

The run phase has **no network**, so the method source must be baked in at build time. The Dockerfile
`git clone`s `github.com/AMRI-Lab/INR-QSM` into `/opt/INR-QSM` (the python package is in the repo's
`inr-qsm/` subdir → `INR_QSM_HOME=/opt/INR-QSM/inr-qsm`) and installs a **CPU** PyTorch wheel.

There are **no recon weights to download** — INR-QSM optimizes per subject. The repo does ship an
**optional** transfer-learning init (`inr-qsm/transfer_learning/…​.pkl`, ~8 MB, used only to speed up
convergence); it comes along with the clone.

```bash
# from the repo root
docker build -t ghcr.io/astewartau/qsm-ci/inr-qsm:v1 algorithms/inr-qsm
docker push  ghcr.io/astewartau/qsm-ci/inr-qsm:v1
```

- For reproducibility, pin the method commit: `--build-arg INR_QSM_REF=<sha>`.
- QSM-CI also builds this folder's Dockerfile at score-time, so a manual push is not strictly
  required — but build it once locally to confirm it succeeds.

### GPU variant (optional — see RUNTIME/GPU CAVEAT)

Change the torch install from the CPU index (`.../whl/cpu`) to CUDA (e.g. `.../whl/cu121`), remove
`ENV CUDA_VISIBLE_DEVICES="-1"` (Dockerfile) and the `export CUDA_VISIBLE_DEVICES=-1` (`run.sh`). Note
the wrapper runs **float32** (CUDA AMP/fp16 from the reference was dropped for CPU compatibility), so
a GPU run is heavier than the paper's fp16 pipeline.

## 2. Smoke-test locally (with ground truth)

```bash
qsm-forward simple bids/          # phantom WITH ground truth
qsm-ci run inr-qsm \
  --localfield lf.nii.gz --mask mask.nii.gz --params params.json \
  --truth chi.nii.gz
```

Confirm: it produces `chimap.nii.gz`, the scale looks like ppm QSM (~±0.1–0.2 in tissue), and the
sign/orientation are correct. To iterate fast during testing, cap epochs: `--set epoch=5`.

## 3. Decisions the human must make ⚠️

- **CPU vs. GPU / iteration cap.** Per-subject optimization (default **50 epochs**, wide/deep SIREN,
  full-volume 3D FFTs) is expensive; the reference used an NVIDIA A6000 (~10 GB VRAM). Time a CPU run
  first; if it exceeds the CI time limit (2 h → DNF), use a GPU runner or lower
  `epoch`/`num_layers`/`hidden_dim_num`.
- **Fidelity deviations** (see README): this wrapper runs a **full-volume** objective rather than the
  paper's **patch-based non-local phase-compensation** loop, and computes the **WG edge weights in
  Python** (TKD-seeded) instead of via **STISuite** (proprietary MATLAB, not shipped). Decide whether
  these approximations are acceptable, or port the patch pipeline for a GPU variant.

## 4. Files in this folder

| File | Role |
|------|------|
| `algorithm.yml` | Manifest: stage `dipole`, image, `run: bash run.sh`, parameters (`epoch`, `star_lr`, `end_lr`, `hidden_dim_num`, `num_layers`, `TV_weight`, `gd_weight`). |
| `Dockerfile` | CPU PyTorch base + `git clone` INR-QSM to `/opt/INR-QSM` (no recon weights). Code is mounted, not COPYed. |
| `run.sh` | Forces CPU, calls `inr_qsm_infer.py /input /output`. |
| `inr_qsm_infer.py` | Reuses the repo's SIREN + dipole kernel + TV/GD losses; runs per-subject optimization; writes `chimap.nii.gz` on the input affine. |
| `README.md` | Method description, units, kernel, deviations, RUNTIME/GPU CAVEAT, assumptions. |
