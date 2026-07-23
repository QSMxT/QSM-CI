# BUILD — MoDIP (`modip`)

This submission is a **scaffold**. The container image is **not** built or pushed, and the pipeline
has **not** been run. This file lists exactly what a human must do to finish.

## 1. Build & push the environment image

The run phase has **no network**, so the method source must be baked in at build time. The Dockerfile
`git clone`s `github.com/sunhongfu/MoDIP` into `/opt/MoDIP` and installs a **CPU** PyTorch wheel.
There are **no weights to download** (MoDIP is untrained — it optimizes per subject).

```bash
# from the repo root
docker build -t ghcr.io/astewartau/qsm-ci/modip:v1 algorithms/modip
docker push  ghcr.io/astewartau/qsm-ci/modip:v1
```

- For reproducibility, pin the method commit: `--build-arg MODIP_REF=<sha>`.
- QSM-CI also builds this folder's Dockerfile at score-time, so a manual push is not strictly
  required for the leaderboard — but build it once locally to confirm it succeeds.

### GPU variant (optional, recommended — see below)

To build a CUDA image, change the torch install in the Dockerfile from the CPU index
(`https://download.pytorch.org/whl/cpu`) to a CUDA one (e.g. `.../whl/cu121`), remove
`ENV CUDA_VISIBLE_DEVICES="-1"`, and drop the `export CUDA_VISIBLE_DEVICES=-1` in `run.sh`.

## 2. Smoke-test locally (with ground truth)

```bash
qsm-forward simple bids/          # phantom WITH ground truth
# feed the localfield/mask/params + truth from bids/derivatives/qsm-forward/ to:
qsm-ci run modip \
  --localfield lf.nii.gz --mask mask.nii.gz --params params.json \
  --truth chi.nii.gz
```

Confirm: it produces `chimap.nii.gz`, the scale looks like ppm QSM (roughly ±0.1–0.2 in tissue), and
the sign is correct.

## 3. Decide the CPU-vs-GPU / iteration-cap question ⚠️

MoDIP **optimizes a network per input volume** (default **500 iterations**). This is the main risk:

- **Time a CPU run first.** If a 500-iteration CPU run exceeds the CI time limit (default 2 h → DNF),
  either:
  - provide a **GPU runner** (GPU variant above), or
  - **cap iterations** via `epoch_num` (e.g. `--set epoch_num=150`) and/or lower `base` — the
    reference ships 100/200/500-iteration examples showing the trade-off.

Record the chosen `epoch_num` default if you change it from 500.

## 4. Files in this folder

| File | Role |
|------|------|
| `algorithm.yml` | Manifest: stage `dipole`, image, `run: bash run.sh`, parameters (`epoch_num`, `lr`, `base`). |
| `Dockerfile` | CPU PyTorch base + `git clone` MoDIP to `/opt/MoDIP` (no weights). Code is mounted, not COPYed. |
| `run.sh` | Forces CPU, calls `modip_infer.py /input /output`. |
| `modip_infer.py` | Loads localfield+mask+params, calls the repo's `inference.run_modip`, masks + writes `chimap.nii.gz` on the input affine. |
| `README.md` | Method description, units, kernel, RUNTIME/GPU CAVEAT, assumptions. |
