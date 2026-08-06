# BUILD — AFTER-QSM (`after-qsm`)

This submission is **packaged but not built or run here**. AFTER-QSM is **GPU-only in practice** (8 GB+
VRAM) and QSM-CI has no GPU runner yet, so it is `ci_skip`ed (see `algorithm.yml` / README). The image
build below is **deferred to a GPU/host** — do not build it on a CPU-only box (the CUDA wheel is large
and there is nothing to gain without a GPU to smoke-test on). This file lists exactly what a human must
do to finish.

## 1. Build & push the environment image

The run phase has **no network**, so the method source + weights must be baked in at build time. The
Dockerfile `git clone`s `github.com/sunhongfu/AFTER-QSM` into `/opt/AFTER-QSM`; the pretrained
checkpoint (`checkpoints/AFTER-QSM.pkl`, ~34 MB) is **committed in the repo**, so it comes along with
the clone — **no separate download step**.

```bash
# from the repo root, on a machine with Docker (GPU host preferred for the smoke test)
docker build -t ghcr.io/astewartau/qsm-ci/after-qsm:v1 algorithms/after-qsm
docker push  ghcr.io/astewartau/qsm-ci/after-qsm:v1
```

- For reproducibility, the method commit is pinned via `ARG AFTERQSM_REF` (currently
  `d29afefc6d556242e498aa7a3ef6a102832ec851`); override with
  `--build-arg AFTERQSM_REF=<sha>`.
- The build `test`s that `checkpoints/AFTER-QSM.pkl` is present after the clone, so a stale/missing
  checkpoint fails the build loudly.
- QSM-CI also builds this folder's Dockerfile at score-time — but since the method is `ci_skip`ed it
  will not be scored until a GPU runner exists.

## 2. Smoke-test (needs a GPU)

On a GPU host, run the repo's own CLI through the image to confirm end-to-end behaviour:

```bash
docker run --rm --gpus all \
  -v "$PWD/algorithms/after-qsm":/algo:ro \
  -v "$PWD/some_localfield_dir":/input:ro \
  -v "$PWD/out":/output \
  ghcr.io/astewartau/qsm-ci/after-qsm:v1 bash /algo/run.sh
```

`/input` must contain `localfield.nii.gz` (ppm). Set `QSMCI_VOXEL_SIZE` / `QSMCI_B0_DIR` to match the
acquisition (defaults `1 1 1` / `0 0 1` axial). Confirm:

- `out/chimap.nii.gz` is written, on the input affine;
- the scale looks like ppm QSM (~±0.1–0.2 in tissue), sign/orientation correct;
- `segment_num` can be raised (`QSMCI_SET_SEGMENT_NUM=8`) if VRAM is tight.

Or, with the CLI once the image is published and a GPU runner exists:

```bash
qsm-forward simple bids/          # phantom WITH ground truth
qsm-ci run after-qsm \
  --localfield lf.nii.gz --params params.json \
  --truth chi.nii.gz
```

## 3. Un-skip when a GPU runner lands ⚠️

Once QSM-CI has a GPU runner and a GPU route in `score.yml`:

1. In `algorithm.yml`, set `ci_skip: false` (or remove it); keep `runner: gpu`.
2. Confirm the image runs under the GPU runner (see §2).
3. Let CI score it — it will then appear on the leaderboard.

## 4. Files in this folder

| File | Role |
|------|------|
| `algorithm.yml` | Manifest: stage `dipole`, image, `run: bash run.sh`, `runner: gpu`, `ci_skip: true`, `parameters` (`segment_num`). |
| `Dockerfile` | CUDA-capable (CPU-optional) PyTorch base + `git clone` AFTER-QSM to `/opt/AFTER-QSM`; committed checkpoint baked via the clone. Code mounted, not COPYed. |
| `run.sh` | Wires `--voxel-size`/`--b0-dir`/`--segment-num` from env, drives the repo's `run.py`, publishes the refined (deblur) map as `chimap.nii.gz`. |
| `README.md` | Method, units, geometry wiring, checkpoint provenance, license, GPU/ci_skip caveat. |
